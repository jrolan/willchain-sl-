"""
Business logic services for Module 5: Verification & Legal Workflow.

# LQ-1: Under Sierra Leone law, what document(s) constitute sufficient proof
#        of executor authority? The minimum evidence standard for CLAIMED_EXECUTOR
#        cases is unresolved and requires confirmation from a qualified legal adviser
#        before this case type is activated in production.
#
# LQ-2: Is a pre-death review approval of any legal significance under Sierra Leone
#        law? The system currently treats it as a professional opinion only, with no
#        release authority. Confirmation required.
#
# LQ-3: Should the system enforce a cooling-off period between a rejected case and
#        a new case from the same initiator? Architecture report mandates no cooling-
#        off (OD-4 Decision), but this is a policy question for the project owner.
#
# LQ-4: Does GDPR or Sierra Leone data-protection law impose a maximum retention
#        period on evidence files after a case reaches a terminal state? If so, the
#        storage design may need revision.
#
# LQ-5: Is there a legal requirement that the assigned verifier be a member of the
#        Sierra Leone Bar Association or hold a specific professional qualification?
#        The system does not verify credentials beyond the LAWYER_VERIFIER role flag.
"""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.accounts.services import log_audit_event
from apps.audit.models import AuditEvent
from apps.beneficiaries.models import WillBeneficiary
from apps.documents.storage import private_document_storage
from apps.documents.validation import validate_upload
from apps.wills.models import Will

from .models import (
    CaseEvidence,
    CaseStatusHistory,
    EligibilityAssessment,
    VerificationCase,
    WillDisclosureAuthorization,
)

# Permitted state transitions map: source_status -> set of allowed target_statuses
PERMITTED_TRANSITIONS = {
    VerificationCase.Status.PENDING_ELIGIBILITY: {
        VerificationCase.Status.OPEN,
        VerificationCase.Status.INFORMATION_REQUIRED,
        VerificationCase.Status.REJECTED,
        VerificationCase.Status.WITHDRAWN,
    },
    VerificationCase.Status.OPEN: {
        VerificationCase.Status.INFORMATION_REQUIRED,
        VerificationCase.Status.UNDER_REVIEW,
        VerificationCase.Status.WITHDRAWN,
    },
    VerificationCase.Status.INFORMATION_REQUIRED: {
        VerificationCase.Status.OPEN,
        VerificationCase.Status.PENDING_ELIGIBILITY,
        VerificationCase.Status.WITHDRAWN,
    },
    VerificationCase.Status.UNDER_REVIEW: {
        VerificationCase.Status.INFORMATION_REQUIRED,
        VerificationCase.Status.APPROVED,
        VerificationCase.Status.REJECTED,
        VerificationCase.Status.WITHDRAWN,
    },
    VerificationCase.Status.APPROVED: set(),
    VerificationCase.Status.REJECTED: set(),
    VerificationCase.Status.WITHDRAWN: set(),
}


def check_pre_death_eligibility(user, will):
    """
    Validates applicant eligibility for a pre-death legal review:
      - Initiator must be the will owner.
      - Will must be in FINALIZED status.
      - No active (non-terminal) pre-death review case can already exist for this will.
    """
    if will is None:
        raise ValidationError({'will': 'A finalized will must be specified for pre-death review.'})

    if will.owner != user:
        raise PermissionDenied('Only the will owner can initiate a pre-death review.')

    if will.status != Will.Status.FINALIZED:
        raise ValidationError({'will': 'Only finalized wills can be submitted for pre-death review.'})

    has_active_case = VerificationCase.objects.filter(
        will=will,
        case_type=VerificationCase.CaseType.PRE_DEATH_REVIEW,
        status__in=VerificationCase.ACTIVE_STATUSES,
    ).exists()
    if has_active_case:
        raise ValidationError({'will': 'An active pre-death review case already exists for this will.'})


def check_post_death_eligibility(user, will):
    """
    Validates applicant eligibility for a post-death beneficiary claim:
      - Initiator must have an active beneficiary relationship on the will.
      - Will must be in FINALIZED status.
    """
    if will is None:
        raise ValidationError({'will': 'A finalized will must be specified for a beneficiary claim.'})

    if will.status != Will.Status.FINALIZED:
        raise ValidationError({'will': 'Only finalized wills can be subject to post-death verification.'})

    # Beneficiary relationship must be ACTIVE
    is_active_beneficiary = WillBeneficiary.objects.filter(
        will=will,
        beneficiary_user=user,
        status=WillBeneficiary.Status.ACTIVE,
    ).exists()

    if not is_active_beneficiary:
        raise PermissionDenied('User is not an active beneficiary for this will.')


def check_executor_claim_eligibility(user, will, claimed_executor_basis=''):
    """
    Validates applicant eligibility for a CLAIMED_EXECUTOR post-death claim:
      - Will must be in FINALIZED status if a will is specified.
      - Basis must not exceed 512 characters.
    """
    if will is not None and will.status != Will.Status.FINALIZED:
        raise ValidationError({'will': 'Only finalized wills can be subject to post-death verification.'})

    if len(claimed_executor_basis) > 512:
        raise ValidationError({'claimed_executor_basis': 'Executor basis must not exceed 512 characters.'})


def transition_case_status(case, target_status, actor, notes='', request=None, audit_event_type=None):
    """
    Internal helper to transition case status, append to CaseStatusHistory,
    and log an audit event.
    """
    allowed_targets = PERMITTED_TRANSITIONS.get(case.status, set())
    if target_status not in allowed_targets:
        raise ValidationError(f'Invalid status transition from {case.status} to {target_status}.')

    old_status = case.status
    case.status = target_status
    if notes:
        if target_status in {VerificationCase.Status.APPROVED, VerificationCase.Status.REJECTED}:
            case.decision_notes = notes
        elif target_status == VerificationCase.Status.INFORMATION_REQUIRED:
            case.information_request_notes = notes

    case.save(update_fields=['status', 'decision_notes', 'information_request_notes', 'updated_at'])

    CaseStatusHistory.objects.create(
        case=case,
        from_status=old_status,
        to_status=target_status,
        actor=actor,
        notes=notes,
    )

    if audit_event_type:
        log_audit_event(
            audit_event_type,
            request=request,
            actor=actor,
            target_user=case.initiator,
            details={
                'case_id': case.pk,
                'from_status': old_status,
                'to_status': target_status,
                'notes': notes,
            },
        )


def validate_linked_prior_case(initiator, linked_prior_case):
    """
    Authorizes a `linked_prior_case` reference on a new case.

    The only caller who may link to a prior case is the prior case's own
    initiator. This is the single relationship the case-creation workflow
    supports: a retry or resubmission after rejection is made by the same
    applicant who filed the original case. It is NOT a universal reference
    field, and it must not be used to expose or attach another user's case.

    Anti-enumeration: callers receive a generic 400 (not 404) so that
    unauthorized users cannot probe for another user's case identifiers.
    """
    if linked_prior_case is None:
        return
    if linked_prior_case.initiator_id != initiator.pk:
        raise ValidationError(
            'The referenced prior case is not accessible from this account.'
        )


def create_case(initiator, will, case_type, submission_type, claimed_executor_basis='', linked_prior_case=None, request=None):
    """
    Creates a new VerificationCase within an atomic transaction, using select_for_update
    to prevent duplicate active cases per will per case_type (OD-4).
    """
    # Authorize the linked prior-case reference before any state is mutated.
    validate_linked_prior_case(initiator, linked_prior_case)

    with transaction.atomic():
        if will:
            # Concurrency safeguard: lock any existing active cases for this will and case_type
            active_conflicts = (
                VerificationCase.objects.select_for_update()
                .filter(
                    will=will,
                    case_type=case_type,
                    status__in=VerificationCase.ACTIVE_STATUSES,
                )
                .exists()
            )
            if active_conflicts:
                raise ValidationError('An active case of this type already exists for this will.')

        # Run eligibility checks based on submission type
        if submission_type == VerificationCase.SubmissionType.OWNER_INITIATED:
            if case_type != VerificationCase.CaseType.PRE_DEATH_REVIEW:
                raise ValidationError({'case_type': 'Owner-initiated cases must be PRE_DEATH_REVIEW.'})
            check_pre_death_eligibility(initiator, will)
            initial_status = VerificationCase.Status.OPEN

        elif submission_type == VerificationCase.SubmissionType.BENEFICIARY_CLAIM:
            if case_type != VerificationCase.CaseType.POST_DEATH_VERIFY:
                raise ValidationError({'case_type': 'Beneficiary claims must be POST_DEATH_VERIFY.'})
            check_post_death_eligibility(initiator, will)
            initial_status = VerificationCase.Status.OPEN

        elif submission_type == VerificationCase.SubmissionType.CLAIMED_EXECUTOR:
            if case_type != VerificationCase.CaseType.POST_DEATH_VERIFY:
                raise ValidationError({'case_type': 'Claimed executor cases must be POST_DEATH_VERIFY.'})
            check_executor_claim_eligibility(initiator, will, claimed_executor_basis)
            # Enters PENDING_ELIGIBILITY state
            initial_status = VerificationCase.Status.PENDING_ELIGIBILITY
        else:
            raise ValidationError({'submission_type': 'Invalid submission type.'})

        case = VerificationCase.objects.create(
            will=will,
            initiator=initiator,
            case_type=case_type,
            submission_type=submission_type,
            status=initial_status,
            claimed_executor_basis=claimed_executor_basis,
            linked_prior_case=linked_prior_case,
        )

        CaseStatusHistory.objects.create(
            case=case,
            from_status='',
            to_status=initial_status,
            actor=initiator,
            notes='Case created.',
        )

        log_audit_event(
            AuditEvent.EventType.VERIFICATION_CASE_CREATED,
            request=request,
            actor=initiator,
            target_user=initiator,
            details={
                'case_id': case.pk,
                'case_type': case_type,
                'submission_type': submission_type,
                'status': initial_status,
            },
        )

        return case


def submit_case(case, actor, request=None):
    """
    Validates minimum evidence and submits a case:
    - Pre-death review: >= 1 evidence file
    - Beneficiary claim: >= 1 file (DEATH_CERTIFICATE or IDENTITY_DOCUMENT)
    - Claimed executor: >= 1 file (IDENTITY_DOCUMENT or PROBATE_DOCUMENT)
    """
    if case.initiator != actor:
        raise PermissionDenied('Only the case initiator can submit the case.')

    evidence_qs = case.evidence.all()
    evidence_count = evidence_qs.count()
    if evidence_count < 1:
        raise ValidationError('At least one evidence file is required before submission.')

    evidence_types = set(evidence_qs.values_list('evidence_type', flat=True))

    if case.submission_type == VerificationCase.SubmissionType.BENEFICIARY_CLAIM:
        required_types = {
            CaseEvidence.EvidenceType.DEATH_CERTIFICATE,
            CaseEvidence.EvidenceType.IDENTITY_DOCUMENT,
        }
        if not (evidence_types & required_types):
            raise ValidationError(
                'Beneficiary claim requires at least one death certificate or identity document.'
            )
    elif case.submission_type == VerificationCase.SubmissionType.CLAIMED_EXECUTOR:
        required_types = {
            CaseEvidence.EvidenceType.IDENTITY_DOCUMENT,
            CaseEvidence.EvidenceType.PROBATE_DOCUMENT,
        }
        if not (evidence_types & required_types):
            raise ValidationError(
                'Claimed executor submission requires at least one identity document or probate document.'
            )

    log_audit_event(
        AuditEvent.EventType.VERIFICATION_CASE_SUBMITTED,
        request=request,
        actor=actor,
        target_user=case.initiator,
        details={'case_id': case.pk, 'evidence_count': evidence_count},
    )
    return case


def assign_lawyer(case, lawyer, actor, request=None):
    """
    Assigns an authorized lawyer to the case (admin only).
    """
    if actor.role != User.Role.ADMINISTRATOR:
        raise PermissionDenied('Only administrators can assign lawyers to verification cases.')

    if lawyer.role != User.Role.LAWYER_VERIFIER:
        raise ValidationError({'lawyer_id': 'Assigned user must have LAWYER_VERIFIER role.'})

    if not lawyer.is_active:
        raise ValidationError({'lawyer_id': 'Assigned lawyer account must be active.'})

    case.assigned_lawyer = lawyer
    case.assigned_at = timezone.now()
    case.save(update_fields=['assigned_lawyer', 'assigned_at', 'updated_at'])

    CaseStatusHistory.objects.create(
        case=case,
        from_status=case.status,
        to_status=case.status,
        actor=actor,
        notes=f'Assigned lawyer: {lawyer.first_name} {lawyer.last_name}'.strip(),
    )

    log_audit_event(
        AuditEvent.EventType.VERIFICATION_CASE_ASSIGNED,
        request=request,
        actor=actor,
        target_user=lawyer,
        details={'case_id': case.pk, 'lawyer_id': lawyer.pk},
    )
    return case


def assess_eligibility(case, lawyer, is_eligible, notes='', request=None):
    """
    Lawyer reviews executor authority claim for a CLAIMED_EXECUTOR case in PENDING_ELIGIBILITY.
    If is_eligible=True, transitions to OPEN.
    If is_eligible=False, transitions to REJECTED.
    """
    if case.assigned_lawyer != lawyer:
        raise PermissionDenied('Only the assigned lawyer can assess eligibility.')

    if case.status != VerificationCase.Status.PENDING_ELIGIBILITY:
        raise ValidationError('Eligibility can only be assessed while case is in PENDING_ELIGIBILITY.')

    assessment, _ = EligibilityAssessment.objects.update_or_create(
        case=case,
        defaults={
            'assessed_by': lawyer,
            'is_eligible': is_eligible,
            'notes': notes,
        },
    )

    target_status = VerificationCase.Status.OPEN if is_eligible else VerificationCase.Status.REJECTED
    transition_case_status(
        case,
        target_status,
        actor=lawyer,
        notes=notes,
        request=request,
        audit_event_type=AuditEvent.EventType.VERIFICATION_ELIGIBILITY_CHECKED,
    )
    return assessment


def begin_review(case, actor, request=None):
    """
    Transitions OPEN -> UNDER_REVIEW (assigned lawyer only).
    """
    if case.assigned_lawyer != actor:
        raise PermissionDenied('Only the assigned lawyer can begin review.')

    transition_case_status(
        case,
        VerificationCase.Status.UNDER_REVIEW,
        actor=actor,
        notes='Review commenced.',
        request=request,
        audit_event_type=AuditEvent.EventType.VERIFICATION_REVIEW_BEGUN,
    )
    return case


def request_information(case, actor, notes, request=None):
    """
    Transitions OPEN or UNDER_REVIEW or PENDING_ELIGIBILITY -> INFORMATION_REQUIRED.
    """
    if case.assigned_lawyer != actor:
        raise PermissionDenied('Only the assigned lawyer can request additional information.')

    if not notes.strip():
        raise ValidationError({'notes': 'Notes explaining the requested information are required.'})

    transition_case_status(
        case,
        VerificationCase.Status.INFORMATION_REQUIRED,
        actor=actor,
        notes=notes,
        request=request,
        audit_event_type=AuditEvent.EventType.VERIFICATION_INFORMATION_REQUESTED,
    )
    return case


def submit_additional_information(case, actor, request=None):
    """
    Transitions INFORMATION_REQUIRED -> OPEN (or PENDING_ELIGIBILITY for claimed executor).
    Requires case initiator.
    """
    if case.initiator != actor:
        raise PermissionDenied('Only the case initiator can resubmit information.')

    if case.status != VerificationCase.Status.INFORMATION_REQUIRED:
        raise ValidationError('Case is not currently awaiting additional information.')

    target_status = (
        VerificationCase.Status.PENDING_ELIGIBILITY
        if case.submission_type == VerificationCase.SubmissionType.CLAIMED_EXECUTOR
        and not hasattr(case, 'eligibility_assessment')
        else VerificationCase.Status.OPEN
    )

    transition_case_status(
        case,
        target_status,
        actor=actor,
        notes='Additional information provided by claimant.',
        request=request,
        audit_event_type=AuditEvent.EventType.VERIFICATION_CASE_RESUBMITTED,
    )
    return case


def record_decision(case, actor, decision, notes='', request=None):
    """
    Records APPROVED or REJECTED decision (assigned lawyer only).
    """
    if case.assigned_lawyer != actor:
        raise PermissionDenied('Only the assigned lawyer can record a decision.')

    if decision not in {VerificationCase.Status.APPROVED, VerificationCase.Status.REJECTED}:
        raise ValidationError({'decision': 'Decision must be APPROVED or REJECTED.'})

    transition_case_status(
        case,
        decision,
        actor=actor,
        notes=notes,
        request=request,
        audit_event_type=AuditEvent.EventType.VERIFICATION_DECISION_RECORDED,
    )
    return case


def withdraw_case(case, actor, request=None):
    """
    Transitions non-terminal case to WITHDRAWN (initiator or admin only).
    """
    if actor != case.initiator and actor.role != User.Role.ADMINISTRATOR:
        raise PermissionDenied('Only the case initiator or an administrator can withdraw the case.')

    if case.status in VerificationCase.TERMINAL_STATUSES:
        raise ValidationError('Terminal cases cannot be withdrawn.')

    transition_case_status(
        case,
        VerificationCase.Status.WITHDRAWN,
        actor=actor,
        notes='Case withdrawn.',
        request=request,
        audit_event_type=AuditEvent.EventType.VERIFICATION_CASE_WITHDRAWN,
    )
    return case


def upload_evidence(case, actor, upload_file, evidence_type, description='', request=None):
    """
    Validates uploaded file via validate_upload, stores in private_document_storage,
    creates CaseEvidence, and logs audit event.
    sufficiency_flag is default False and NEVER set here.
    """
    if case.initiator != actor:
        raise PermissionDenied('Only the case initiator can upload evidence.')

    if case.status in VerificationCase.TERMINAL_STATUSES:
        raise ValidationError('Cannot upload evidence to a case in a terminal status.')

    if evidence_type not in CaseEvidence.EvidenceType.values:
        raise ValidationError({'evidence_type': 'Invalid evidence type.'})

    validated = validate_upload(upload_file)
    storage_key = private_document_storage.save(validated)

    evidence = CaseEvidence.objects.create(
        case=case,
        uploaded_by=actor,
        evidence_type=evidence_type,
        description=description,
        original_filename=validated.filename,
        storage_key=storage_key,
        media_type=validated.media_type,
        file_size=validated.file_size,
        checksum_sha256=validated.checksum_sha256,
        sufficiency_flag=False,
    )

    log_audit_event(
        AuditEvent.EventType.VERIFICATION_EVIDENCE_UPLOADED,
        request=request,
        actor=actor,
        target_user=case.initiator,
        details={
            'case_id': case.pk,
            'evidence_id': evidence.pk,
            'evidence_type': evidence_type,
        },
    )
    return evidence


def set_evidence_sufficiency(evidence, actor, sufficiency_flag, request=None):
    """
    Allows the assigned lawyer to set or clear the sufficiency_flag.

    Emits VERIFICATION_EVIDENCE_SUFFICIENCY_CHANGED only when the flag actually
    changes; repeated calls with the same value are idempotent and produce no
    audit event (avoids misleading audit history).
    """
    if evidence.case.assigned_lawyer != actor:
        raise PermissionDenied('Only the assigned lawyer can set evidence sufficiency.')

    new_flag = bool(sufficiency_flag)
    old_flag = bool(evidence.sufficiency_flag)

    if old_flag == new_flag:
        return evidence

    evidence.sufficiency_flag = new_flag
    evidence.save(update_fields=['sufficiency_flag'])

    log_audit_event(
        AuditEvent.EventType.VERIFICATION_EVIDENCE_SUFFICIENCY_CHANGED,
        request=request,
        actor=actor,
        target_user=evidence.case.initiator,
        details={
            'case_id': evidence.case_id,
            'evidence_id': evidence.pk,
            'old_sufficiency': old_flag,
            'new_sufficiency': new_flag,
        },
    )
    return evidence


def authorize_will_disclosure(case, actor, upload_file, request=None):
    """
    Authorizes a will copy disclosure for pre-death review:
      - actor must be will owner.
      - case_type must be PRE_DEATH_REVIEW.
      - creates or replaces WillDisclosureAuthorization with a dedicated copy in private storage.
      - logs BOTH VERIFICATION_EVIDENCE_UPLOADED and WILL_DISCLOSURE_AUTHORIZED audit events.
    """
    if case.case_type != VerificationCase.CaseType.PRE_DEATH_REVIEW:
        raise ValidationError('Will disclosure authorization is only permitted for pre-death review.')

    if case.will is None or case.will.owner != actor:
        raise PermissionDenied('Only the will owner can authorize will disclosure.')

    validated = validate_upload(upload_file)
    storage_key = private_document_storage.save(validated)

    # If previous authorization existed, deactivate and update
    existing = getattr(case, 'disclosure_authorization', None)
    if existing:
        existing.is_active = True
        existing.revoked_at = None
        existing.storage_key = storage_key
        existing.original_filename = validated.filename
        existing.media_type = validated.media_type
        existing.file_size = validated.file_size
        existing.checksum_sha256 = validated.checksum_sha256
        existing.save()
        auth = existing
    else:
        auth = WillDisclosureAuthorization.objects.create(
            case=case,
            authorised_by=actor,
            storage_key=storage_key,
            original_filename=validated.filename,
            media_type=validated.media_type,
            file_size=validated.file_size,
            checksum_sha256=validated.checksum_sha256,
            is_active=True,
        )

    # Distinct audit events
    log_audit_event(
        AuditEvent.EventType.VERIFICATION_EVIDENCE_UPLOADED,
        request=request,
        actor=actor,
        target_user=actor,
        details={'case_id': case.pk, 'disclosure_auth_id': auth.pk},
    )
    log_audit_event(
        AuditEvent.EventType.WILL_DISCLOSURE_AUTHORIZED,
        request=request,
        actor=actor,
        target_user=actor,
        details={'case_id': case.pk, 'disclosure_auth_id': auth.pk},
    )

    return auth


def revoke_will_disclosure(case, actor, request=None):
    """
    Revokes the active will copy disclosure (will owner only).
    """
    if case.will is None or case.will.owner != actor:
        raise PermissionDenied('Only the will owner can revoke will disclosure.')

    auth = getattr(case, 'disclosure_authorization', None)
    if not auth or not auth.is_active:
        raise ValidationError('No active will disclosure exists for this case.')

    auth.is_active = False
    auth.revoked_at = timezone.now()
    auth.save(update_fields=['is_active', 'revoked_at'])

    log_audit_event(
        AuditEvent.EventType.WILL_DISCLOSURE_REVOKED,
        request=request,
        actor=actor,
        target_user=actor,
        details={'case_id': case.pk, 'disclosure_auth_id': auth.pk},
    )
    return auth

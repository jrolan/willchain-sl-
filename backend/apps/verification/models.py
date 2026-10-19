from django.conf import settings
from django.db import models
from django.db.models import Q


class VerificationCase(models.Model):
    """
    Central record for a verification or legal-review case.

    Two discriminator fields control case behaviour:
      - case_type: PRE_DEATH_REVIEW or POST_DEATH_VERIFY
      - submission_type: OWNER_INITIATED, BENEFICIARY_CLAIM, or CLAIMED_EXECUTOR

    State machine (see architecture report §4.2 for full transition table):
      PENDING_ELIGIBILITY → OPEN → INFORMATION_REQUIRED → UNDER_REVIEW → APPROVED
                                                                       → REJECTED
                         → WITHDRAWN (from any non-terminal state)

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

    class CaseType(models.TextChoices):
        PRE_DEATH_REVIEW = 'PRE_DEATH_REVIEW', 'Pre-death review'
        POST_DEATH_VERIFY = 'POST_DEATH_VERIFY', 'Post-death verification'

    class SubmissionType(models.TextChoices):
        OWNER_INITIATED = 'OWNER_INITIATED', 'Owner initiated'
        BENEFICIARY_CLAIM = 'BENEFICIARY_CLAIM', 'Beneficiary claim'
        CLAIMED_EXECUTOR = 'CLAIMED_EXECUTOR', 'Claimed executor'

    class Status(models.TextChoices):
        PENDING_ELIGIBILITY = 'PENDING_ELIGIBILITY', 'Pending eligibility'
        OPEN = 'OPEN', 'Open'
        INFORMATION_REQUIRED = 'INFORMATION_REQUIRED', 'Information required'
        UNDER_REVIEW = 'UNDER_REVIEW', 'Under review'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        WITHDRAWN = 'WITHDRAWN', 'Withdrawn'

    ACTIVE_STATUSES = [
        Status.PENDING_ELIGIBILITY,
        Status.OPEN,
        Status.INFORMATION_REQUIRED,
        Status.UNDER_REVIEW,
    ]

    TERMINAL_STATUSES = [
        Status.APPROVED,
        Status.REJECTED,
        Status.WITHDRAWN,
    ]

    case_type = models.CharField(max_length=32, choices=CaseType.choices, db_index=True)
    submission_type = models.CharField(max_length=32, choices=SubmissionType.choices)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING_ELIGIBILITY,
        db_index=True,
    )
    will = models.ForeignKey(
        'wills.Will',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='verification_cases',
    )
    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='initiated_verification_cases',
    )
    assigned_lawyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_verification_cases',
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    # LQ-1: The basis field is metadata only; it is NOT a legal determination.
    claimed_executor_basis = models.CharField(max_length=512, blank=True)
    decision_notes = models.TextField(blank=True)
    information_request_notes = models.TextField(blank=True)
    linked_prior_case = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subsequent_cases',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=['will', 'case_type'],
                condition=Q(status__in=[
                    'PENDING_ELIGIBILITY', 'OPEN', 'INFORMATION_REQUIRED', 'UNDER_REVIEW',
                ]),
                name='unique_active_case_per_will_per_type',
            ),
        ]
        indexes = [
            models.Index(fields=['status'], name='verif_case_status_idx'),
            models.Index(fields=['will', 'status'], name='verif_case_will_status_idx'),
            models.Index(fields=['initiator', 'status'], name='verif_case_init_status_idx'),
            models.Index(fields=['assigned_lawyer', 'status'], name='verif_case_lawyer_status_idx'),
        ]

    def __str__(self):
        return f'VerificationCase #{self.pk} [{self.case_type}] status={self.status}'


class CaseStatusHistory(models.Model):
    """
    Append-only log of every status transition on a VerificationCase.
    Rows are never updated or deleted — see architecture report §3 Decision 3.
    """
    case = models.ForeignKey(
        VerificationCase,
        on_delete=models.CASCADE,
        related_name='status_history',
    )
    from_status = models.CharField(max_length=32, blank=True)
    to_status = models.CharField(max_length=32)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='case_status_changes',
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ('created_at',)

    def __str__(self):
        return f'Case #{self.case_id}: {self.from_status} → {self.to_status}'


class CaseEvidence(models.Model):
    """
    A private evidence file attached to a VerificationCase.
    storage_key is NEVER exposed through any API response.
    sufficiency_flag may only be set by the assigned LAWYER_VERIFIER (never by upload).
    """

    class EvidenceType(models.TextChoices):
        DEATH_CERTIFICATE = 'DEATH_CERTIFICATE', 'Death certificate'
        IDENTITY_DOCUMENT = 'IDENTITY_DOCUMENT', 'Identity document'
        PROBATE_DOCUMENT = 'PROBATE_DOCUMENT', 'Probate document'
        RELATIONSHIP_PROOF = 'RELATIONSHIP_PROOF', 'Relationship proof'
        WILL_COPY = 'WILL_COPY', 'Will copy'
        OTHER = 'OTHER', 'Other'

    case = models.ForeignKey(
        VerificationCase,
        on_delete=models.CASCADE,
        related_name='evidence',
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_case_evidence',
    )
    evidence_type = models.CharField(max_length=32, choices=EvidenceType.choices)
    description = models.CharField(max_length=255, blank=True)
    original_filename = models.CharField(max_length=255)
    # storage_key is intentionally excluded from all serializers — see architecture §4.5
    storage_key = models.CharField(max_length=80, unique=True)
    media_type = models.CharField(max_length=64)
    file_size = models.PositiveBigIntegerField()
    checksum_sha256 = models.CharField(max_length=64)
    # sufficiency_flag is set by the assigned lawyer only — never by upload or automation
    sufficiency_flag = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.CheckConstraint(
                condition=Q(file_size__gt=0),
                name='case_evidence_file_size_positive',
            ),
        ]

    def __str__(self):
        return f'Evidence #{self.pk} [{self.evidence_type}] for case #{self.case_id}'


class WillDisclosureAuthorization(models.Model):
    """
    Records an explicit owner opt-in to share a will copy with the assigned lawyer.
    Only valid for case_type = PRE_DEATH_REVIEW (enforced in services.py).
    storage_key is NEVER exposed through any API response.
    After revocation, lawyer download returns 403; the physical file is retained for audit.
    """
    case = models.OneToOneField(
        VerificationCase,
        on_delete=models.CASCADE,
        related_name='disclosure_authorization',
    )
    authorised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='disclosure_authorizations',
    )
    # storage_key is intentionally excluded from all serializers — see architecture §4.5
    storage_key = models.CharField(max_length=80, unique=True)
    original_filename = models.CharField(max_length=255)
    media_type = models.CharField(max_length=64)
    file_size = models.PositiveBigIntegerField()
    checksum_sha256 = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True, db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'WillDisclosureAuthorization for case #{self.case_id} (active={self.is_active})'


class EligibilityAssessment(models.Model):
    """
    A lawyer's eligibility determination for a CLAIMED_EXECUTOR case.
    assessed_by must be the case's assigned_lawyer (enforced in services.py).
    """
    case = models.OneToOneField(
        VerificationCase,
        on_delete=models.CASCADE,
        related_name='eligibility_assessment',
    )
    assessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='eligibility_assessments',
    )
    is_eligible = models.BooleanField()
    notes = models.TextField(blank=True)
    assessed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'EligibilityAssessment for case #{self.case_id}: eligible={self.is_eligible}'


"""
Comprehensive test suite for Module 5: Verification & Legal Workflow.
Covers:
  - OD-1: Executor claim, eligibility assessment, minimum evidence, basis field
  - OD-2: Pre-death review, finalized will requirement, disclosure authorization, separation of audit events
  - OD-3: Minimum evidence per case type, sufficiency flag lawyer-only, storage key privacy
  - OD-4: Intra-case resubmission, new case after rejection with prior case linkage, duplicate prevention
  - OD-5: Lawyer assignment, public serializer privacy (display_name and assigned_at only)
  - OD-6: Module 8 status interface, exclusion of pre-death review, no will content or title
  - Security regressions: unauthenticated/inactive accounts, IDOR isolation, role permissions
"""

import io
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from pypdf import PdfWriter
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.beneficiaries.models import WillBeneficiary
from apps.wills.models import Will
from apps.audit.models import AuditEvent
from .models import CaseEvidence, CaseStatusHistory, EligibilityAssessment, VerificationCase, WillDisclosureAuthorization
from .services import create_case, transition_case_status


def valid_pdf_content():
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


PDF_BYTES = valid_pdf_content()


def make_test_file(name='test_doc.pdf', content=PDF_BYTES, content_type='application/pdf'):
    return SimpleUploadedFile(name, content, content_type=content_type)


class VerificationModuleTests(APITestCase):
    def setUp(self):
        self.temp_storage = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(PRIVATE_DOCUMENT_ROOT=Path(self.temp_storage.name))
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.temp_storage.cleanup)

        # Users
        self.owner = self.create_user('owner@example.com', role=User.Role.OWNER)
        self.beneficiary = self.create_user('beneficiary@example.com', role=User.Role.BENEFICIARY)
        self.lawyer = self.create_user('lawyer@example.com', role=User.Role.LAWYER_VERIFIER)
        self.other_lawyer = self.create_user('other_lawyer@example.com', role=User.Role.LAWYER_VERIFIER)
        self.admin = self.create_user('admin@example.com', role=User.Role.ADMINISTRATOR)
        self.unrelated = self.create_user('unrelated@example.com', role=User.Role.MEMBER)

        # Finalized Will
        self.finalized_will = Will.objects.create(
            owner=self.owner,
            title='Last Will and Testament',
            content={'body': 'Confidential will content.'},
            status=Will.Status.DRAFT,
        )
        self.finalized_will.finalize()

        # Draft Will
        self.draft_will = Will.objects.create(
            owner=self.owner,
            title='Draft Will',
            content={'body': 'Draft body.'},
            status=Will.Status.DRAFT,
        )

        # Beneficiary relationship on finalized will
        self.beneficiary_rel = WillBeneficiary.objects.create(
            will=self.finalized_will,
            beneficiary_user=self.beneficiary,
            normalized_email=self.beneficiary.email,
            status=WillBeneficiary.Status.ACTIVE,
        )

    def create_user(self, email, role=User.Role.MEMBER, **overrides):
        values = {
            'first_name': 'Test',
            'last_name': 'User',
            'password': 'Strong-password-123!',
            'account_status': User.AccountStatus.ACTIVE,
            'email_verified': True,
            'role': role,
        }
        values.update(overrides)
        password = values.pop('password')
        return User.objects.create_user(email=email, password=password, **values)

    # -------------------------------------------------------------------------
    # OD-1: Executor Claims and Eligibility Assessment
    # -------------------------------------------------------------------------

    def test_claimed_executor_enters_pending_eligibility(self):
        self.client.force_authenticate(self.unrelated)
        url = reverse('verification:case-list')
        response = self.client.post(url, {
            'case_type': VerificationCase.CaseType.POST_DEATH_VERIFY,
            'submission_type': VerificationCase.SubmissionType.CLAIMED_EXECUTOR,
            'will': self.finalized_will.pk,
            'claimed_executor_basis': 'Named executor in test will clause 4.',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        case_data = response.data['data']
        self.assertEqual(case_data['status'], VerificationCase.Status.PENDING_ELIGIBILITY)
        self.assertEqual(case_data['claimed_executor_basis'], 'Named executor in test will clause 4.')

    def test_claimed_executor_cannot_access_will_in_pending_state(self):
        self.client.force_authenticate(self.unrelated)
        url = reverse('verification:case-list')
        response = self.client.post(url, {
            'case_type': VerificationCase.CaseType.POST_DEATH_VERIFY,
            'submission_type': VerificationCase.SubmissionType.CLAIMED_EXECUTOR,
            'will': self.finalized_will.pk,
            'claimed_executor_basis': 'Named executor in test will clause 4.',
        })
        case_id = response.data['data']['id']

        detail_url = reverse('verification:case-detail', kwargs={'pk': case_id})
        detail_res = self.client.get(detail_url)
        self.assertNotIn('content', detail_res.data['data'])
        self.assertNotIn('title', detail_res.data['data'])
        self.assertEqual(detail_res.data['data']['will'], self.finalized_will.pk)

    def test_eligibility_assessment_transitions_to_open_when_eligible(self):
        # Create case
        self.client.force_authenticate(self.unrelated)
        res = self.client.post(reverse('verification:case-list'), {
            'case_type': VerificationCase.CaseType.POST_DEATH_VERIFY,
            'submission_type': VerificationCase.SubmissionType.CLAIMED_EXECUTOR,
            'will': self.finalized_will.pk,
            'claimed_executor_basis': 'Sole executor',
        })
        case_id = res.data['data']['id']

        # Assign lawyer via admin
        self.client.force_authenticate(self.admin)
        self.client.post(reverse('verification:case-assign-lawyer', kwargs={'pk': case_id}), {
            'lawyer_id': self.lawyer.pk,
        })

        # Lawyer assesses eligibility as True
        self.client.force_authenticate(self.lawyer)
        assess_url = reverse('verification:case-assess-eligibility', kwargs={'pk': case_id})
        assess_res = self.client.post(assess_url, {
            'is_eligible': True,
            'notes': 'Letters of administration verified.',
        })
        self.assertEqual(assess_res.status_code, status.HTTP_200_OK)

        case = VerificationCase.objects.get(pk=case_id)
        self.assertEqual(case.status, VerificationCase.Status.OPEN)

    def test_ineligible_executor_transitions_to_rejected(self):
        self.client.force_authenticate(self.unrelated)
        res = self.client.post(reverse('verification:case-list'), {
            'case_type': VerificationCase.CaseType.POST_DEATH_VERIFY,
            'submission_type': VerificationCase.SubmissionType.CLAIMED_EXECUTOR,
            'will': self.finalized_will.pk,
            'claimed_executor_basis': 'Purported executor',
        })
        case_id = res.data['data']['id']

        # Assign lawyer
        self.client.force_authenticate(self.admin)
        self.client.post(reverse('verification:case-assign-lawyer', kwargs={'pk': case_id}), {
            'lawyer_id': self.lawyer.pk,
        })

        # Lawyer rejects eligibility
        self.client.force_authenticate(self.lawyer)
        assess_res = self.client.post(reverse('verification:case-assess-eligibility', kwargs={'pk': case_id}), {
            'is_eligible': False,
            'notes': 'Insufficient grant of probate evidence.',
        })
        self.assertEqual(assess_res.status_code, status.HTTP_200_OK)

        case = VerificationCase.objects.get(pk=case_id)
        self.assertEqual(case.status, VerificationCase.Status.REJECTED)

    def test_non_lawyer_cannot_assess_eligibility(self):
        case = VerificationCase.objects.create(
            initiator=self.unrelated,
            case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
            submission_type=VerificationCase.SubmissionType.CLAIMED_EXECUTOR,
            status=VerificationCase.Status.PENDING_ELIGIBILITY,
            assigned_lawyer=self.lawyer,
        )
        self.client.force_authenticate(self.owner)
        url = reverse('verification:case-assess-eligibility', kwargs={'pk': case.pk})
        res = self.client.post(url, {'is_eligible': True})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_different_lawyer_cannot_assess_eligibility(self):
        case = VerificationCase.objects.create(
            initiator=self.unrelated,
            case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
            submission_type=VerificationCase.SubmissionType.CLAIMED_EXECUTOR,
            status=VerificationCase.Status.PENDING_ELIGIBILITY,
            assigned_lawyer=self.lawyer,
        )
        self.client.force_authenticate(self.other_lawyer)
        url = reverse('verification:case-assess-eligibility', kwargs={'pk': case.pk})
        res = self.client.post(url, {'is_eligible': True})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_executor_claim_requires_minimum_evidence_to_submit(self):
        case = VerificationCase.objects.create(
            initiator=self.unrelated,
            case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
            submission_type=VerificationCase.SubmissionType.CLAIMED_EXECUTOR,
            status=VerificationCase.Status.PENDING_ELIGIBILITY,
        )
        self.client.force_authenticate(self.unrelated)
        url = reverse('verification:case-submit', kwargs={'pk': case.pk})
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # -------------------------------------------------------------------------
    # OD-2: Pre-Death Review Workflow and Disclosure
    # -------------------------------------------------------------------------

    def test_pre_death_review_requires_owner(self):
        self.client.force_authenticate(self.unrelated)
        res = self.client.post(reverse('verification:case-list'), {
            'case_type': VerificationCase.CaseType.PRE_DEATH_REVIEW,
            'submission_type': VerificationCase.SubmissionType.OWNER_INITIATED,
            'will': self.finalized_will.pk,
        })
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_pre_death_review_requires_finalized_will(self):
        self.client.force_authenticate(self.owner)
        res = self.client.post(reverse('verification:case-list'), {
            'case_type': VerificationCase.CaseType.PRE_DEATH_REVIEW,
            'submission_type': VerificationCase.SubmissionType.OWNER_INITIATED,
            'will': self.draft_will.pk,
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_pre_death_case_rejected(self):
        self.client.force_authenticate(self.owner)
        res1 = self.client.post(reverse('verification:case-list'), {
            'case_type': VerificationCase.CaseType.PRE_DEATH_REVIEW,
            'submission_type': VerificationCase.SubmissionType.OWNER_INITIATED,
            'will': self.finalized_will.pk,
        })
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        res2 = self.client.post(reverse('verification:case-list'), {
            'case_type': VerificationCase.CaseType.PRE_DEATH_REVIEW,
            'submission_type': VerificationCase.SubmissionType.OWNER_INITIATED,
            'will': self.finalized_will.pk,
        })
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_lawyer_assignment_does_not_expose_will_title_or_content(self):
        self.client.force_authenticate(self.owner)
        res = self.client.post(reverse('verification:case-list'), {
            'case_type': VerificationCase.CaseType.PRE_DEATH_REVIEW,
            'submission_type': VerificationCase.SubmissionType.OWNER_INITIATED,
            'will': self.finalized_will.pk,
        })
        case_id = res.data['data']['id']

        self.client.force_authenticate(self.admin)
        self.client.post(reverse('verification:case-assign-lawyer', kwargs={'pk': case_id}), {
            'lawyer_id': self.lawyer.pk,
        })

        self.client.force_authenticate(self.lawyer)
        detail_res = self.client.get(reverse('verification:case-detail', kwargs={'pk': case_id}))
        self.assertNotIn('title', detail_res.data['data'])
        self.assertNotIn('content', detail_res.data['data'])
        self.assertEqual(detail_res.data['data']['will'], self.finalized_will.pk)

    def test_owner_can_authorize_disclosure_and_creates_separate_audit_events(self):
        self.client.force_authenticate(self.owner)
        res = self.client.post(reverse('verification:case-list'), {
            'case_type': VerificationCase.CaseType.PRE_DEATH_REVIEW,
            'submission_type': VerificationCase.SubmissionType.OWNER_INITIATED,
            'will': self.finalized_will.pk,
        })
        case_id = res.data['data']['id']

        initial_auth_events = AuditEvent.objects.filter(
            event_type=AuditEvent.EventType.WILL_DISCLOSURE_AUTHORIZED
        ).count()
        initial_upload_events = AuditEvent.objects.filter(
            event_type=AuditEvent.EventType.VERIFICATION_EVIDENCE_UPLOADED
        ).count()

        upload = make_test_file('will_copy.pdf')
        auth_url = reverse('verification:case-authorize-disclosure', kwargs={'pk': case_id})
        auth_res = self.client.post(auth_url, {'file': upload}, format='multipart')
        self.assertEqual(auth_res.status_code, status.HTTP_200_OK)

        self.assertEqual(
            AuditEvent.objects.filter(event_type=AuditEvent.EventType.WILL_DISCLOSURE_AUTHORIZED).count(),
            initial_auth_events + 1,
        )
        self.assertEqual(
            AuditEvent.objects.filter(event_type=AuditEvent.EventType.VERIFICATION_EVIDENCE_UPLOADED).count(),
            initial_upload_events + 1,
        )

    def test_lawyer_download_disclosure_respects_revocation(self):
        self.client.force_authenticate(self.owner)
        res = self.client.post(reverse('verification:case-list'), {
            'case_type': VerificationCase.CaseType.PRE_DEATH_REVIEW,
            'submission_type': VerificationCase.SubmissionType.OWNER_INITIATED,
            'will': self.finalized_will.pk,
        })
        case_id = res.data['data']['id']

        # Authorize disclosure
        upload = make_test_file('will_copy.pdf')
        self.client.post(reverse('verification:case-authorize-disclosure', kwargs={'pk': case_id}), {'file': upload}, format='multipart')

        # Assign lawyer
        self.client.force_authenticate(self.admin)
        self.client.post(reverse('verification:case-assign-lawyer', kwargs={'pk': case_id}), {'lawyer_id': self.lawyer.pk})

        # Lawyer downloads active disclosure
        self.client.force_authenticate(self.lawyer)
        dl_url = reverse('verification:case-disclosure-download', kwargs={'pk': case_id})
        dl_res = self.client.get(dl_url)
        self.assertEqual(dl_res.status_code, status.HTTP_200_OK)
        # Consume streaming content and close response to release Windows file lock
        _ = b''.join(dl_res.streaming_content)
        dl_res.close()

        # Owner revokes
        self.client.force_authenticate(self.owner)
        revoke_url = reverse('verification:case-revoke-disclosure', kwargs={'pk': case_id})
        rev_res = self.client.post(revoke_url)
        self.assertEqual(rev_res.status_code, status.HTTP_200_OK)

        # Lawyer download is now forbidden
        self.client.force_authenticate(self.lawyer)
        dl_res2 = self.client.get(dl_url)
        self.assertEqual(dl_res2.status_code, status.HTTP_403_FORBIDDEN)

    def test_disclosure_not_permitted_for_post_death_case(self):
        case = VerificationCase.objects.create(
            initiator=self.beneficiary,
            will=self.finalized_will,
            case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
            submission_type=VerificationCase.SubmissionType.BENEFICIARY_CLAIM,
            status=VerificationCase.Status.OPEN,
        )
        self.client.force_authenticate(self.owner)
        url = reverse('verification:case-authorize-disclosure', kwargs={'pk': case.pk})
        res = self.client.post(url, {'file': make_test_file()}, format='multipart')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # -------------------------------------------------------------------------
    # OD-3: Minimum Evidence and Lawyer Sufficiency
    # -------------------------------------------------------------------------

    def test_case_initiation_and_evidence_upload(self):
        self.client.force_authenticate(self.beneficiary)
        case_res = self.client.post(reverse('verification:case-list'), {
            'case_type': VerificationCase.CaseType.POST_DEATH_VERIFY,
            'submission_type': VerificationCase.SubmissionType.BENEFICIARY_CLAIM,
            'will': self.finalized_will.pk,
        })
        case_id = case_res.data['data']['id']

        # Upload evidence
        ev_url = reverse('verification:case-evidence', kwargs={'pk': case_id})
        ev_res = self.client.post(ev_url, {
            'evidence_type': CaseEvidence.EvidenceType.DEATH_CERTIFICATE,
            'description': 'Official death certificate',
            'file': make_test_file('death_cert.pdf'),
        }, format='multipart')
        self.assertEqual(ev_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ev_res.data['data']['sufficiency_flag'], False)
        self.assertNotIn('storage_key', ev_res.data['data'])

    def test_case_cannot_be_submitted_without_minimum_evidence(self):
        self.client.force_authenticate(self.beneficiary)
        case_res = self.client.post(reverse('verification:case-list'), {
            'case_type': VerificationCase.CaseType.POST_DEATH_VERIFY,
            'submission_type': VerificationCase.SubmissionType.BENEFICIARY_CLAIM,
            'will': self.finalized_will.pk,
        })
        case_id = case_res.data['data']['id']

        sub_url = reverse('verification:case-submit', kwargs={'pk': case_id})
        sub_res = self.client.post(sub_url)
        self.assertEqual(sub_res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sufficiency_flag_set_by_lawyer_only(self):
        case = VerificationCase.objects.create(
            initiator=self.beneficiary,
            will=self.finalized_will,
            case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
            submission_type=VerificationCase.SubmissionType.BENEFICIARY_CLAIM,
            status=VerificationCase.Status.OPEN,
            assigned_lawyer=self.lawyer,
        )
        evidence = CaseEvidence.objects.create(
            case=case,
            uploaded_by=self.beneficiary,
            evidence_type=CaseEvidence.EvidenceType.DEATH_CERTIFICATE,
            original_filename='cert.pdf',
            storage_key='a' * 64 + '.pdf',
            media_type='application/pdf',
            file_size=1024,
            checksum_sha256='b' * 64,
            sufficiency_flag=False,
        )

        suff_url = reverse('verification:case-evidence-sufficiency', kwargs={'pk': case.pk, 'evidence_pk': evidence.pk})

        # Beneficiary cannot set sufficiency
        self.client.force_authenticate(self.beneficiary)
        res_ben = self.client.post(suff_url, {'sufficiency_flag': True})
        self.assertEqual(res_ben.status_code, status.HTTP_403_FORBIDDEN)

        # Assigned lawyer can set sufficiency
        self.client.force_authenticate(self.lawyer)
        res_law = self.client.post(suff_url, {'sufficiency_flag': True})
        self.assertEqual(res_law.status_code, status.HTTP_200_OK)
        self.assertTrue(res_law.data['data']['sufficiency_flag'])

    # -------------------------------------------------------------------------
    # OD-4: Controlled Resubmission and New Cases
    # -------------------------------------------------------------------------

    def test_resubmission_within_case(self):
        case = VerificationCase.objects.create(
            initiator=self.beneficiary,
            will=self.finalized_will,
            case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
            submission_type=VerificationCase.SubmissionType.BENEFICIARY_CLAIM,
            status=VerificationCase.Status.INFORMATION_REQUIRED,
            assigned_lawyer=self.lawyer,
        )
        self.client.force_authenticate(self.beneficiary)
        url = reverse('verification:case-resubmit', kwargs={'pk': case.pk})
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        case.refresh_from_db()
        self.assertEqual(case.status, VerificationCase.Status.OPEN)

    def test_new_case_after_rejection_links_prior_case(self):
        prior_case = VerificationCase.objects.create(
            initiator=self.beneficiary,
            will=self.finalized_will,
            case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
            submission_type=VerificationCase.SubmissionType.BENEFICIARY_CLAIM,
            status=VerificationCase.Status.REJECTED,
        )

        self.client.force_authenticate(self.beneficiary)
        res = self.client.post(reverse('verification:case-list'), {
            'case_type': VerificationCase.CaseType.POST_DEATH_VERIFY,
            'submission_type': VerificationCase.SubmissionType.BENEFICIARY_CLAIM,
            'will': self.finalized_will.pk,
            'linked_prior_case': prior_case.pk,
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['data']['linked_prior_case'], prior_case.pk)

    # -------------------------------------------------------------------------
    # OD-5: Assigned Lawyer Identity Privacy
    # -------------------------------------------------------------------------

    def test_assigned_lawyer_public_serializer_exposes_only_approved_fields(self):
        case = VerificationCase.objects.create(
            initiator=self.owner,
            will=self.finalized_will,
            case_type=VerificationCase.CaseType.PRE_DEATH_REVIEW,
            submission_type=VerificationCase.SubmissionType.OWNER_INITIATED,
            status=VerificationCase.Status.OPEN,
            assigned_lawyer=self.lawyer,
        )
        self.client.force_authenticate(self.owner)
        res = self.client.get(reverse('verification:case-detail', kwargs={'pk': case.pk}))
        lawyer_display = res.data['data']['assigned_lawyer_display']
        self.assertIsNotNone(lawyer_display)
        self.assertIn('display_name', lawyer_display)
        self.assertIn('assigned_at', lawyer_display)
        self.assertNotIn('email', lawyer_display)
        self.assertNotIn('phone_number', lawyer_display)
        self.assertNotIn('avatar', lawyer_display)
        self.assertNotIn('id', lawyer_display)

    # -------------------------------------------------------------------------
    # OD-6: Module 8 Release Conditions Separation
    # -------------------------------------------------------------------------

    def test_module8_status_endpoint_returns_only_approved_post_death_cases(self):
        # Create and approve a POST_DEATH_VERIFY case
        case = VerificationCase.objects.create(
            initiator=self.beneficiary,
            will=self.finalized_will,
            case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
            submission_type=VerificationCase.SubmissionType.BENEFICIARY_CLAIM,
            status=VerificationCase.Status.APPROVED,
            assigned_lawyer=self.lawyer,
        )

        self.client.force_authenticate(self.beneficiary)
        url = reverse('verification:will-verification-status', kwargs={'will_pk': self.finalized_will.pk})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data['data']
        self.assertEqual(data['case_id'], case.pk)
        self.assertEqual(data['will_id'], self.finalized_will.pk)
        self.assertEqual(data['status'], VerificationCase.Status.APPROVED)
        self.assertNotIn('title', data)
        self.assertNotIn('content', data)

    def test_pre_death_review_approval_not_returned_by_module8_endpoint(self):
        # Create and approve a PRE_DEATH_REVIEW case
        VerificationCase.objects.create(
            initiator=self.owner,
            will=self.finalized_will,
            case_type=VerificationCase.CaseType.PRE_DEATH_REVIEW,
            submission_type=VerificationCase.SubmissionType.OWNER_INITIATED,
            status=VerificationCase.Status.APPROVED,
            assigned_lawyer=self.lawyer,
        )

        self.client.force_authenticate(self.owner)
        url = reverse('verification:will-verification-status', kwargs={'will_pk': self.finalized_will.pk})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # -------------------------------------------------------------------------
    # Security Regressions
    # -------------------------------------------------------------------------

    def test_unauthenticated_user_cannot_access_cases(self):
        self.client.logout()
        res = self.client.get(reverse('verification:case-list'))
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_account_cannot_access_verification(self):
        inactive_user = self.create_user(
            'inactive@example.com',
            account_status=User.AccountStatus.INACTIVE,
        )
        self.client.force_authenticate(inactive_user)
        res = self.client.get(reverse('verification:case-list'))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_idor_case_not_visible_to_unrelated_user(self):
        case = VerificationCase.objects.create(
            initiator=self.owner,
            will=self.finalized_will,
            case_type=VerificationCase.CaseType.PRE_DEATH_REVIEW,
            submission_type=VerificationCase.SubmissionType.OWNER_INITIATED,
            status=VerificationCase.Status.OPEN,
        )
        self.client.force_authenticate(self.unrelated)
        res = self.client.get(reverse('verification:case-detail', kwargs={'pk': case.pk}))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------------------
    # CRITICAL-1: Pre-death Evidence Download Authorization Gating
    # -------------------------------------------------------------------------

    def _create_pre_death_case_with_evidence(self):
        """Helper to set up a pre-death review case, assigned lawyer, and uploaded evidence."""
        self.client.force_authenticate(self.owner)
        res = self.client.post(reverse('verification:case-list'), {
            'case_type': VerificationCase.CaseType.PRE_DEATH_REVIEW,
            'submission_type': VerificationCase.SubmissionType.OWNER_INITIATED,
            'will': self.finalized_will.pk,
        })
        case_id = res.data['data']['id']

        # Upload evidence
        ev_upload = make_test_file('owner_evidence.pdf')
        ev_res = self.client.post(
            reverse('verification:case-evidence', kwargs={'pk': case_id}),
            {
                'evidence_type': CaseEvidence.EvidenceType.IDENTITY_DOCUMENT,
                'description': 'Testator national ID copy',
                'file': ev_upload,
            },
            format='multipart',
        )
        evidence_id = ev_res.data['data']['id']

        # Assign lawyer via admin
        self.client.force_authenticate(self.admin)
        self.client.post(
            reverse('verification:case-assign-lawyer', kwargs={'pk': case_id}),
            {'lawyer_id': self.lawyer.pk},
        )

        return case_id, evidence_id

    def test_assigned_lawyer_cannot_download_pre_death_evidence_when_disclosure_never_authorized(self):
        case_id, evidence_id = self._create_pre_death_case_with_evidence()

        # Assigned lawyer attempts to download evidence without disclosure authorization: expect 403
        self.client.force_authenticate(self.lawyer)
        dl_url = reverse('verification:case-evidence-download', kwargs={'pk': case_id, 'evidence_pk': evidence_id})
        dl_res = self.client.get(dl_url)
        try:
            self.assertEqual(dl_res.status_code, status.HTTP_403_FORBIDDEN)
        finally:
            if hasattr(dl_res, 'streaming_content'):
                _ = b''.join(dl_res.streaming_content)
            dl_res.close()

    def test_assigned_lawyer_cannot_download_pre_death_evidence_after_disclosure_revoked(self):
        case_id, evidence_id = self._create_pre_death_case_with_evidence()

        # Authorize disclosure
        self.client.force_authenticate(self.owner)
        upload = make_test_file('will_copy.pdf')
        auth_res = self.client.post(
            reverse('verification:case-authorize-disclosure', kwargs={'pk': case_id}),
            {'file': upload},
            format='multipart',
        )
        self.assertEqual(auth_res.status_code, status.HTTP_200_OK)

        # Owner revokes disclosure
        revoke_res = self.client.post(
            reverse('verification:case-revoke-disclosure', kwargs={'pk': case_id})
        )
        self.assertEqual(revoke_res.status_code, status.HTTP_200_OK)

        # Assigned lawyer attempts to download evidence after revocation: expect 403
        self.client.force_authenticate(self.lawyer)
        dl_url = reverse('verification:case-evidence-download', kwargs={'pk': case_id, 'evidence_pk': evidence_id})
        dl_res = self.client.get(dl_url)
        try:
            self.assertEqual(dl_res.status_code, status.HTTP_403_FORBIDDEN)
        finally:
            if hasattr(dl_res, 'streaming_content'):
                _ = b''.join(dl_res.streaming_content)
            dl_res.close()

    def test_owner_can_download_own_pre_death_evidence(self):
        case_id, evidence_id = self._create_pre_death_case_with_evidence()

        # Owner downloads their own evidence: expect 200
        self.client.force_authenticate(self.owner)
        dl_url = reverse('verification:case-evidence-download', kwargs={'pk': case_id, 'evidence_pk': evidence_id})
        dl_res = self.client.get(dl_url)
        try:
            self.assertEqual(dl_res.status_code, status.HTTP_200_OK)
        finally:
            if hasattr(dl_res, 'streaming_content'):
                _ = b''.join(dl_res.streaming_content)
            dl_res.close()

    def test_assigned_lawyer_can_download_pre_death_evidence_with_active_disclosure(self):
        case_id, evidence_id = self._create_pre_death_case_with_evidence()

        # Authorize disclosure
        self.client.force_authenticate(self.owner)
        upload = make_test_file('will_copy.pdf')
        auth_res = self.client.post(
            reverse('verification:case-authorize-disclosure', kwargs={'pk': case_id}),
            {'file': upload},
            format='multipart',
        )
        self.assertEqual(auth_res.status_code, status.HTTP_200_OK)

        # Assigned lawyer downloads evidence with active disclosure: expect 200
        self.client.force_authenticate(self.lawyer)
        dl_url = reverse('verification:case-evidence-download', kwargs={'pk': case_id, 'evidence_pk': evidence_id})
        dl_res = self.client.get(dl_url)
        try:
            self.assertEqual(dl_res.status_code, status.HTTP_200_OK)
        finally:
            if hasattr(dl_res, 'streaming_content'):
                _ = b''.join(dl_res.streaming_content)
            dl_res.close()

    # -------------------------------------------------------------------------
    # HIGH-1: Module 8 status endpoint object-level authorization scoping
    # -------------------------------------------------------------------------

    def _create_approved_post_death_case(self, initiator=None, lawyer=None):
        """Helper: creates an APPROVED POST_DEATH_VERIFY case on the finalized will."""
        case = VerificationCase.objects.create(
            initiator=initiator or self.beneficiary,
            will=self.finalized_will,
            case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
            submission_type=VerificationCase.SubmissionType.BENEFICIARY_CLAIM,
            status=VerificationCase.Status.APPROVED,
            assigned_lawyer=lawyer or self.lawyer,
        )
        CaseStatusHistory.objects.create(
            case=case,
            from_status=VerificationCase.Status.UNDER_REVIEW,
            to_status=VerificationCase.Status.APPROVED,
            actor=lawyer or self.lawyer,
            notes='Approved.',
        )
        return case

    def _status_url(self, will=None):
        return reverse('verification:will-verification-status', kwargs={'will_pk': (will or self.finalized_will).pk})

    def test_module8_status_rejected_by_unrelated_user(self):
        self._create_approved_post_death_case()
        self.client.force_authenticate(self.unrelated)
        res = self.client.get(self._status_url())
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_module8_status_rejected_by_beneficiary_of_the_will(self):
        # A single APPROVED case whose initiator is the will owner. The beneficiary
        # is an active beneficiary on the will but is neither owner, initiator, nor
        # assigned lawyer, so the status must remain hidden from them.
        self._create_approved_post_death_case(initiator=self.owner, lawyer=self.lawyer)
        self.client.force_authenticate(self.beneficiary)
        res = self.client.get(self._status_url())
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_module8_status_allowed_for_will_owner(self):
        self._create_approved_post_death_case(initiator=self.owner, lawyer=self.lawyer)
        self.client.force_authenticate(self.owner)
        res = self.client.get(self._status_url())
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_module8_status_allowed_for_case_initiator(self):
        self._create_approved_post_death_case(initiator=self.beneficiary, lawyer=self.lawyer)
        self.client.force_authenticate(self.beneficiary)
        res = self.client.get(self._status_url())
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_module8_status_allowed_for_assigned_lawyer(self):
        self._create_approved_post_death_case(initiator=self.owner, lawyer=self.lawyer)
        self.client.force_authenticate(self.lawyer)
        res = self.client.get(self._status_url())
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_module8_status_allowed_for_administrator(self):
        self._create_approved_post_death_case(initiator=self.owner, lawyer=self.lawyer)
        self.client.force_authenticate(self.admin)
        res = self.client.get(self._status_url())
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_module8_status_unrelated_user_cannot_enumerate_other_wills(self):
        # A second will owned by another user, with an approved case on it.
        other_owner = self.create_user('other_owner@example.com', role=User.Role.OWNER)
        other_will = Will.objects.create(
            owner=other_owner,
            title='Other Will',
            content={'body': 'other'},
            status=Will.Status.DRAFT,
        )
        other_will.finalize()
        VerificationCase.objects.create(
            initiator=other_owner,
            will=other_will,
            case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
            submission_type=VerificationCase.SubmissionType.OWNER_INITIATED,
            status=VerificationCase.Status.APPROVED,
            assigned_lawyer=self.lawyer,
        )
        self.client.force_authenticate(self.unrelated)
        res = self.client.get(self._status_url(will=other_will))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # -------------------------------------------------------------------------
    # Phase 3: Service authorization and object-level access audit
    # -------------------------------------------------------------------------

    def _make_post_death_case(self, initiator=None, lawyer=None):
        return VerificationCase.objects.create(
            initiator=initiator or self.beneficiary,
            will=self.finalized_will,
            case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
            submission_type=VerificationCase.SubmissionType.BENEFICIARY_CLAIM,
            status=VerificationCase.Status.OPEN,
            assigned_lawyer=lawyer or self.lawyer,
        )

    def _make_pre_death_case(self, lawyer=None):
        return VerificationCase.objects.create(
            initiator=self.owner,
            will=self.finalized_will,
            case_type=VerificationCase.CaseType.PRE_DEATH_REVIEW,
            submission_type=VerificationCase.SubmissionType.OWNER_INITIATED,
            status=VerificationCase.Status.OPEN,
            assigned_lawyer=lawyer or self.lawyer,
        )

    def _evidence_on(self, case, evidence_type=CaseEvidence.EvidenceType.IDENTITY_DOCUMENT,
                     uploaded_by=None, filename='evidence.pdf', sufficiency_flag=False):
        return CaseEvidence.objects.create(
            case=case,
            uploaded_by=uploaded_by or case.initiator,
            evidence_type=evidence_type,
            original_filename=filename,
            storage_key='c' * 64 + '.pdf',
            media_type='application/pdf',
            file_size=1024,
            checksum_sha256='d' * 64,
            sufficiency_flag=False,
        )

    def test_unrelated_user_cannot_set_sufficiency_on_another_case(self):
        case = self._make_post_death_case(initiator=self.owner)
        evidence = self._evidence_on(case)
        self.client.force_authenticate(self.unrelated)
        res = self.client.post(
            reverse('verification:case-evidence-sufficiency', kwargs={'pk': case.pk, 'evidence_pk': evidence.pk}),
            {'sufficiency_flag': True},
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        evidence.refresh_from_db()
        self.assertFalse(evidence.sufficiency_flag)

    def test_non_assigned_lawyer_cannot_set_sufficiency(self):
        case = self._make_post_death_case(initiator=self.owner, lawyer=self.lawyer)
        evidence = self._evidence_on(case)
        self.client.force_authenticate(self.other_lawyer)
        res = self.client.post(
            reverse('verification:case-evidence-sufficiency', kwargs={'pk': case.pk, 'evidence_pk': evidence.pk}),
            {'sufficiency_flag': True},
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_beneficiary_cannot_begin_review_or_record_decision_on_case(self):
        case = self._make_post_death_case(initiator=self.owner, lawyer=self.lawyer)
        self.client.force_authenticate(self.beneficiary)
        review = self.client.post(reverse('verification:case-begin-review', kwargs={'pk': case.pk}))
        decision = self.client.post(
            reverse('verification:case-decision', kwargs={'pk': case.pk}),
            {'decision': VerificationCase.Status.APPROVED},
        )
        self.assertEqual(review.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(decision.status_code, status.HTTP_403_FORBIDDEN)

    def test_inactive_assigned_lawyer_cannot_perform_review_actions(self):
        suspended_lawyer = self.create_user('suspended-lawyer@example.com', role=User.Role.LAWYER_VERIFIER,
                                            account_status=User.AccountStatus.SUSPENDED)
        case = self._make_post_death_case(initiator=self.owner, lawyer=suspended_lawyer)
        self.client.force_authenticate(suspended_lawyer)
        review = self.client.post(reverse('verification:case-begin-review', kwargs={'pk': case.pk}))
        information = self.client.post(
            reverse('verification:case-request-information', kwargs={'pk': case.pk}),
            {'notes': 'needs more'},
        )
        decision = self.client.post(
            reverse('verification:case-decision', kwargs={'pk': case.pk}),
            {'decision': VerificationCase.Status.APPROVED},
        )
        assess = self.client.post(
            reverse('verification:case-assess-eligibility', kwargs={'pk': case.pk}),
            {'is_eligible': True},
        )
        self.assertEqual(review.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(information.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(decision.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(assess.status_code, status.HTTP_403_FORBIDDEN)

    def test_cross_case_disclosure_authorize_and_revoke_blocked_for_unrelated_user(self):
        pre_case = self._make_pre_death_case(lawyer=self.lawyer)
        # Only the will owner (self.owner) may authorize/revoke; unrelated user is blocked.
        self.client.force_authenticate(self.unrelated)
        upload = make_test_file('will_copy.pdf')
        auth = self.client.post(
            reverse('verification:case-authorize-disclosure', kwargs={'pk': pre_case.pk}),
            {'file': upload}, format='multipart',
        )
        revoke = self.client.post(reverse('verification:case-revoke-disclosure', kwargs={'pk': pre_case.pk}))
        download = self.client.get(reverse('verification:case-disclosure-download', kwargs={'pk': pre_case.pk}))
        self.assertEqual(auth.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(revoke.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(download.status_code, status.HTTP_403_FORBIDDEN)

    def test_unrelated_user_cannot_upload_evidence_to_another_case(self):
        case = self._make_post_death_case(initiator=self.owner)
        self.client.force_authenticate(self.unrelated)
        res = self.client.post(
            reverse('verification:case-evidence', kwargs={'pk': case.pk}),
            {
                'evidence_type': CaseEvidence.EvidenceType.IDENTITY_DOCUMENT,
                'file': make_test_file('evidence.pdf'),
            },
            format='multipart',
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_assigned_lawyer_can_download_evidence_design_confirmed(self):
        # Intended behavior per module5-plan.md (CanViewCase): the assigned lawyer may download evidence
        # when an active disclosure authorization exists for a pre-death case.
        pre_case = self._make_pre_death_case(lawyer=self.lawyer)

        # Authorize disclosure (owner only)
        self.client.force_authenticate(self.owner)
        upload = make_test_file('will_copy.pdf')
        self.client.post(
            reverse('verification:case-authorize-disclosure', kwargs={'pk': pre_case.pk}),
            {'file': upload}, format='multipart',
        )

        # Upload real evidence through the API so the file exists in private storage.
        self.client.force_authenticate(self.owner)
        ev_res = self.client.post(
            reverse('verification:case-evidence', kwargs={'pk': pre_case.pk}),
            {
                'evidence_type': CaseEvidence.EvidenceType.IDENTITY_DOCUMENT,
                'file': make_test_file('evidence.pdf'),
            },
            format='multipart',
        )
        self.assertEqual(ev_res.status_code, status.HTTP_201_CREATED)
        evidence_id = ev_res.data['data']['id']

        # Assigned lawyer downloads evidence: expect 200 (disclosure active).
        self.client.force_authenticate(self.lawyer)
        res = self.client.get(reverse('verification:case-evidence-download', kwargs={'pk': pre_case.pk, 'evidence_pk': evidence_id}))
        try:
            self.assertEqual(res.status_code, status.HTTP_200_OK)
        finally:
            if hasattr(res, 'streaming_content'):
                _ = b''.join(res.streaming_content)
            res.close()

    # -------------------------------------------------------------------------
    # Phase 4: Audit event integrity and evidence-sufficiency auditing
    # -------------------------------------------------------------------------

    def _audit_events_for(self, event_type):
        return AuditEvent.objects.filter(event_type=event_type)

    def test_begin_review_records_review_begun_event_not_assigned_event(self):
        case = self._make_post_death_case(initiator=self.owner, lawyer=self.lawyer)
        self.client.force_authenticate(self.lawyer)
        res = self.client.post(reverse('verification:case-begin-review', kwargs={'pk': case.pk}))
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertEqual(self._audit_events_for(AuditEvent.EventType.VERIFICATION_REVIEW_BEGUN).count(), 1)
        self.assertEqual(self._audit_events_for(AuditEvent.EventType.VERIFICATION_CASE_ASSIGNED).count(), 0)

        event = self._audit_events_for(AuditEvent.EventType.VERIFICATION_REVIEW_BEGUN).get()
        self.assertEqual(event.actor, self.lawyer)
        self.assertEqual(event.target_user, case.initiator)

    def test_request_information_records_information_requested_event_not_decision_event(self):
        case = self._make_post_death_case(initiator=self.owner, lawyer=self.lawyer)
        self.client.force_authenticate(self.lawyer)
        res = self.client.post(
            reverse('verification:case-request-information', kwargs={'pk': case.pk}),
            {'notes': 'Please provide the death certificate.'},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertEqual(self._audit_events_for(AuditEvent.EventType.VERIFICATION_INFORMATION_REQUESTED).count(), 1)
        self.assertEqual(self._audit_events_for(AuditEvent.EventType.VERIFICATION_DECISION_RECORDED).count(), 0)

        event = self._audit_events_for(AuditEvent.EventType.VERIFICATION_INFORMATION_REQUESTED).get()
        self.assertEqual(event.actor, self.lawyer)
        self.assertEqual(event.target_user, case.initiator)

    def test_failed_review_action_creates_no_misleading_success_event(self):
        case = self._make_post_death_case(initiator=self.owner, lawyer=self.lawyer)
        before = AuditEvent.objects.count()
        # Non-assigned lawyer cannot begin review.
        self.client.force_authenticate(self.other_lawyer)
        res = self.client.post(reverse('verification:case-begin-review', kwargs={'pk': case.pk}))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(AuditEvent.objects.count(), before)
        self.assertEqual(self._audit_events_for(AuditEvent.EventType.VERIFICATION_REVIEW_BEGUN).count(), 0)

    def test_sufficiency_change_records_sufficiency_changed_event_with_old_and_new_values(self):
        case = self._make_post_death_case(initiator=self.owner, lawyer=self.lawyer)
        evidence = self._evidence_on(case, sufficiency_flag=False)
        self.client.force_authenticate(self.lawyer)
        res = self.client.post(
            reverse('verification:case-evidence-sufficiency', kwargs={'pk': case.pk, 'evidence_pk': evidence.pk}),
            {'sufficiency_flag': True},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        events = self._audit_events_for(AuditEvent.EventType.VERIFICATION_EVIDENCE_SUFFICIENCY_CHANGED)
        self.assertEqual(events.count(), 1)
        event = events.get()
        self.assertEqual(event.actor, self.lawyer)
        self.assertEqual(event.target_user, case.initiator)
        self.assertEqual(event.details.get('case_id'), case.pk)
        self.assertEqual(event.details.get('evidence_id'), evidence.pk)
        self.assertEqual(event.details.get('old_sufficiency'), False)
        self.assertEqual(event.details.get('new_sufficiency'), True)

    def test_sufficiency_change_event_contains_no_sensitive_data(self):
        case = self._make_post_death_case(initiator=self.owner, lawyer=self.lawyer)
        evidence = self._evidence_on(case, sufficiency_flag=False)
        self.client.force_authenticate(self.lawyer)
        self.client.post(
            reverse('verification:case-evidence-sufficiency', kwargs={'pk': case.pk, 'evidence_pk': evidence.pk}),
            {'sufficiency_flag': True},
        )
        event = self._audit_events_for(AuditEvent.EventType.VERIFICATION_EVIDENCE_SUFFICIENCY_CHANGED).get()
        details_str = str(event.details)
        self.assertNotIn('storage_key', details_str)
        self.assertNotIn(evidence.original_filename, details_str)
        self.assertNotIn('content', details_str)
        self.assertNotIn('will', details_str)
        self.assertNotIn('password', details_str)

    def test_unauthorized_sufficiency_change_creates_no_success_audit_event(self):
        case = self._make_post_death_case(initiator=self.owner, lawyer=self.lawyer)
        evidence = self._evidence_on(case, sufficiency_flag=False)
        before = AuditEvent.objects.count()
        self.client.force_authenticate(self.unrelated)
        res = self.client.post(
            reverse('verification:case-evidence-sufficiency', kwargs={'pk': case.pk, 'evidence_pk': evidence.pk}),
            {'sufficiency_flag': True},
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(AuditEvent.objects.count(), before)
        self.assertEqual(self._audit_events_for(AuditEvent.EventType.VERIFICATION_EVIDENCE_SUFFICIENCY_CHANGED).count(), 0)
        evidence.refresh_from_db()
        self.assertFalse(evidence.sufficiency_flag)

    def test_idempotent_sufficiency_change_does_not_create_misleading_audit_history(self):
        case = self._make_post_death_case(initiator=self.owner, lawyer=self.lawyer)
        evidence = self._evidence_on(case, sufficiency_flag=False)
        self.client.force_authenticate(self.lawyer)
        # First change: False -> True
        self.client.post(
            reverse('verification:case-evidence-sufficiency', kwargs={'pk': case.pk, 'evidence_pk': evidence.pk}),
            {'sufficiency_flag': True},
        )
        # Repeat with the same value: no value change, so no new event.
        self.client.post(
            reverse('verification:case-evidence-sufficiency', kwargs={'pk': case.pk, 'evidence_pk': evidence.pk}),
            {'sufficiency_flag': True},
        )
        self.assertEqual(self._audit_events_for(AuditEvent.EventType.VERIFICATION_EVIDENCE_SUFFICIENCY_CHANGED).count(), 1)

    # -------------------------------------------------------------------------
    # Phase 5: Final state-machine and IDOR regression tests
    # -------------------------------------------------------------------------

    def _make_executor_case(self, initiator=None, lawyer=None, will=None,
                            status=VerificationCase.Status.INFORMATION_REQUIRED,
                            basis='Named executor in test will clause 4.'):
        return VerificationCase.objects.create(
            initiator=initiator or self.unrelated,
            will=will,
            case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
            submission_type=VerificationCase.SubmissionType.CLAIMED_EXECUTOR,
            status=status,
            assigned_lawyer=lawyer or self.lawyer,
            claimed_executor_basis=basis,
        )

    def _resubmit(self, case, actor):
        self.client.force_authenticate(actor)
        return self.client.post(
            reverse('verification:case-resubmit', kwargs={'pk': case.pk}),
        )

    # ---- Section 1: Executor resubmission state coverage ----

    def test_executor_resubmission_without_assessment_returns_to_pending_eligibility(self):
        # CLAIMED_EXECUTOR case in INFORMATION_REQUIRED, no eligibility assessment yet.
        case = self._make_executor_case()
        self.assertFalse(EligibilityAssessment.objects.filter(case=case).exists())
        res = self._resubmit(case, self.unrelated)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        case.refresh_from_db()
        self.assertEqual(case.status, VerificationCase.Status.PENDING_ELIGIBILITY)

    def test_executor_resubmission_with_assessment_transitions_to_open(self):
        # CLAIMED_EXECUTOR case with an existing eligibility assessment -> OPEN.
        case = self._make_executor_case()
        EligibilityAssessment.objects.create(case=case, assessed_by=self.lawyer,
                                             is_eligible=True, notes='Letters of administration verified.')
        res = self._resubmit(case, self.unrelated)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        case.refresh_from_db()
        self.assertEqual(case.status, VerificationCase.Status.OPEN)
        self.assertTrue(EligibilityAssessment.objects.filter(case=case).exists())

    def test_executor_resubmission_enforces_initiator_only(self):
        case = self._make_executor_case(initiator=self.unrelated)
        before = AuditEvent.objects.count()
        res = self._resubmit(case, self.owner)  # owner is not the initiator
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        case.refresh_from_db()
        self.assertEqual(case.status, VerificationCase.Status.INFORMATION_REQUIRED)
        self.assertEqual(AuditEvent.objects.count(), before)

    def test_executor_resubmission_blocked_when_not_awaiting_information(self):
        case = self._make_executor_case(status=VerificationCase.Status.OPEN)
        res = self._resubmit(case, self.unrelated)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        case.refresh_from_db()
        self.assertEqual(case.status, VerificationCase.Status.OPEN)

    def test_executor_resubmission_terminal_case_rejected(self):
        # Terminal cases cannot be resubmitted (state machine prohibits INFORMATION_REQUIRED
        # target from a terminal source).
        case = self._make_executor_case(status=VerificationCase.Status.APPROVED)
        before = AuditEvent.objects.count()
        res = self._resubmit(case, self.unrelated)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        case.refresh_from_db()
        self.assertEqual(case.status, VerificationCase.Status.APPROVED)
        self.assertEqual(AuditEvent.objects.count(), before)

    # ---- Section 2: Invalid state transitions ----

    def test_approved_to_open_transition_rejected_with_history_unchanged(self):
        case = self._create_approved_post_death_case(initiator=self.owner, lawyer=self.lawyer)
        before_history = CaseStatusHistory.objects.count()
        before_events = AuditEvent.objects.count()
        with self.assertRaises(ValidationError):
            transition_case_status(case, VerificationCase.Status.OPEN, actor=self.lawyer,
                                   notes='Attempted reopening.')
        case.refresh_from_db()
        self.assertEqual(case.status, VerificationCase.Status.APPROVED)
        self.assertEqual(CaseStatusHistory.objects.count(), before_history)
        self.assertEqual(AuditEvent.objects.count(), before_events)

    def test_open_to_approved_without_review_workflow_rejected(self):
        # OPEN -> APPROVED bypasses UNDER_REVIEW and is not a permitted target.
        case = self._make_post_death_case(initiator=self.owner, lawyer=self.lawyer)  # OPEN
        self.client.force_authenticate(self.lawyer)
        res = self.client.post(reverse('verification:case-decision', kwargs={'pk': case.pk}),
                               {'decision': VerificationCase.Status.APPROVED,
                                'notes': 'Direct approval without review.'})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        case.refresh_from_db()
        self.assertEqual(case.status, VerificationCase.Status.OPEN)

    def test_second_decision_after_terminal_decision_rejected(self):
        # An already-terminal APPROVED case cannot receive another decision.
        case = self._create_approved_post_death_case(initiator=self.owner, lawyer=self.lawyer)
        before_history = CaseStatusHistory.objects.count()
        before_events = AuditEvent.objects.count()
        self.client.force_authenticate(self.lawyer)
        res = self.client.post(reverse('verification:case-decision', kwargs={'pk': case.pk}),
                               {'decision': VerificationCase.Status.REJECTED,
                                'notes': 'Second decision after approval.'})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        case.refresh_from_db()
        self.assertEqual(case.status, VerificationCase.Status.APPROVED)
        self.assertEqual(CaseStatusHistory.objects.count(), before_history)
        self.assertEqual(AuditEvent.objects.count(), before_events)

    def test_rejected_to_open_transition_rejected(self):
        case = VerificationCase.objects.create(
            initiator=self.owner, will=self.finalized_will,
            case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
            submission_type=VerificationCase.SubmissionType.BENEFICIARY_CLAIM,
            status=VerificationCase.Status.REJECTED,
            assigned_lawyer=self.lawyer,
        )
        before_history = CaseStatusHistory.objects.count()
        before_events = AuditEvent.objects.count()
        with self.assertRaises(ValidationError):
            transition_case_status(case, VerificationCase.Status.OPEN, actor=self.lawyer,
                                   notes='Reopening rejected case.')
        case.refresh_from_db()
        self.assertEqual(case.status, VerificationCase.Status.REJECTED)
        self.assertEqual(CaseStatusHistory.objects.count(), before_history)
        self.assertEqual(AuditEvent.objects.count(), before_events)

    # ---- Section 3: linked_prior_case tampering ----

    def test_valid_linked_prior_case_from_same_initiator_still_works(self):
        # Duplicate executor-claim policy for null-will cases remains deferred;
        # a same-initiator prior-case link is accepted.
        prior = VerificationCase.objects.create(
            initiator=self.unrelated, will=None,
            case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
            submission_type=VerificationCase.SubmissionType.CLAIMED_EXECUTOR,
            status=VerificationCase.Status.REJECTED,
            claimed_executor_basis='Prior claim basis.',
        )
        self.client.force_authenticate(self.unrelated)
        res = self.client.post(reverse('verification:case-list'), {
            'case_type': VerificationCase.CaseType.POST_DEATH_VERIFY,
            'submission_type': VerificationCase.SubmissionType.CLAIMED_EXECUTOR,
            'claimed_executor_basis': 'New claim basis.',
            'linked_prior_case': prior.pk,
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['data']['linked_prior_case'], prior.pk)

    def test_unauthorized_linked_prior_case_is_rejected(self):
        # USER A owns a case; USER B (unrelated) attempts to cite USER A's case PK
        # as linked_prior_case on a new CLAIMED_EXECUTOR case (will=None, so no
        # will-based scoping applies). Current implementation has no authorization
        # check on linked_prior_case, so this exposes an IDOR.
        prior = VerificationCase.objects.create(
            initiator=self.owner, will=self.finalized_will,
            case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
            submission_type=VerificationCase.SubmissionType.OWNER_INITIATED,
            status=VerificationCase.Status.REJECTED,
            assigned_lawyer=self.lawyer,
        )
        before_cases = VerificationCase.objects.count()
        before_events = AuditEvent.objects.count()
        self.client.force_authenticate(self.unrelated)
        res = self.client.post(reverse('verification:case-list'), {
            'case_type': VerificationCase.CaseType.POST_DEATH_VERIFY,
            'submission_type': VerificationCase.SubmissionType.CLAIMED_EXECUTOR,
            'claimed_executor_basis': 'Tampered link attempt.',
            'linked_prior_case': prior.pk,
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(VerificationCase.objects.count(), before_cases)
        self.assertEqual(AuditEvent.objects.count(), before_events)
        # Anti-enumeration: the error body must not disclose that the referenced
        # case exists, nor reveal its initiator, will, or case type.
        body = str(res.data).lower()
        self.assertNotIn(str(prior.pk), body)
        self.assertNotIn(self.owner.email, body)
        self.assertNotIn(self.finalized_will.title.lower(), body)
        self.assertNotIn('pre_death_review', body)

    def test_nonexistent_linked_prior_case_is_rejected_without_disclosure(self):
        # A PK that does not exist at all must also be rejected with the same
        # generic error, so probing for arbitrary case IDs is not informative.
        before_cases = VerificationCase.objects.count()
        before_events = AuditEvent.objects.count()
        self.client.force_authenticate(self.unrelated)
        res = self.client.post(reverse('verification:case-list'), {
            'case_type': VerificationCase.CaseType.POST_DEATH_VERIFY,
            'submission_type': VerificationCase.SubmissionType.CLAIMED_EXECUTOR,
            'claimed_executor_basis': 'Nonexistent prior case.',
            'linked_prior_case': 999999,
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(VerificationCase.objects.count(), before_cases)
        self.assertEqual(AuditEvent.objects.count(), before_events)

    def test_linked_prior_case_cannot_cross_unrelated_will(self):
        # Even when the caller IS the prior case's initiator, the new case must
        # not be allowed to link across an unrelated will if the established
        # workflow ties the link to the same applicant. Here the prior case is
        # on the owner's will and the new case is claimed-executor with a
        # different will; the link is rejected because the caller is not the
        # prior case's initiator.
        prior = VerificationCase.objects.create(
            initiator=self.owner, will=self.finalized_will,
            case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
            submission_type=VerificationCase.SubmissionType.OWNER_INITIATED,
            status=VerificationCase.Status.REJECTED,
            assigned_lawyer=self.lawyer,
        )
        before_cases = VerificationCase.objects.count()
        self.client.force_authenticate(self.unrelated)
        res = self.client.post(reverse('verification:case-list'), {
            'case_type': VerificationCase.CaseType.POST_DEATH_VERIFY,
            'submission_type': VerificationCase.SubmissionType.CLAIMED_EXECUTOR,
            'will': self.finalized_will.pk,
            'claimed_executor_basis': 'Cross-will link attempt.',
            'linked_prior_case': prior.pk,
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(VerificationCase.objects.count(), before_cases)

    def test_service_layer_enforcement_cannot_bypass_serializer(self):
        # The service entry point is reachable directly; it must enforce the
        # same authorization rule so no other code path can create the link.
        prior = VerificationCase.objects.create(
            initiator=self.owner, will=self.finalized_will,
            case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
            submission_type=VerificationCase.SubmissionType.OWNER_INITIATED,
            status=VerificationCase.Status.REJECTED,
            assigned_lawyer=self.lawyer,
        )
        before_cases = VerificationCase.objects.count()
        before_events = AuditEvent.objects.count()
        with self.assertRaises(ValidationError):
            create_case(
                initiator=self.unrelated,
                will=None,
                case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
                submission_type=VerificationCase.SubmissionType.CLAIMED_EXECUTOR,
                claimed_executor_basis='Direct service bypass attempt.',
                linked_prior_case=prior,
            )
        self.assertEqual(VerificationCase.objects.count(), before_cases)
        self.assertEqual(AuditEvent.objects.count(), before_events)

    def test_same_initiator_link_with_null_will_remains_supported(self):
        # The established null-will claimed-executor retry workflow (deferred
        # duplicate policy) must continue to link a prior case the caller owns.
        prior = VerificationCase.objects.create(
            initiator=self.unrelated, will=None,
            case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
            submission_type=VerificationCase.SubmissionType.CLAIMED_EXECUTOR,
            status=VerificationCase.Status.REJECTED,
            claimed_executor_basis='Prior claim basis.',
        )
        self.client.force_authenticate(self.unrelated)
        res = self.client.post(reverse('verification:case-list'), {
            'case_type': VerificationCase.CaseType.POST_DEATH_VERIFY,
            'submission_type': VerificationCase.SubmissionType.CLAIMED_EXECUTOR,
            'claimed_executor_basis': 'New claim basis.',
            'linked_prior_case': prior.pk,
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['data']['linked_prior_case'], prior.pk)

    # ---- Section 4: Safe query optimization ----

    def test_resubmission_prefetch_avoids_extra_eligibility_assessment_query(self):
        case = self._make_executor_case()
        EligibilityAssessment.objects.create(case=case, assessed_by=self.lawyer,
                                             is_eligible=True, notes='ok')
        # Without prefetch, `hasattr(case, 'eligibility_assessment')` issues a query.
        case_plain = VerificationCase.objects.get(pk=case.pk)
        with self.assertNumQueries(1):
            hasattr(case_plain, 'eligibility_assessment')
        # With select_related('eligibility_assessment'), no extra query is issued.
        case_prefetched = VerificationCase.objects.select_related(
            'eligibility_assessment').get(pk=case.pk)
        with self.assertNumQueries(0):
            hasattr(case_prefetched, 'eligibility_assessment')

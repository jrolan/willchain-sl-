from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from django.core import mail
from django.test import override_settings
from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.wills.models import Will
from .models import BeneficiaryInvitation, WillBeneficiary


class BeneficiaryModuleTests(APITestCase):
    def active_user(self, **overrides):
        values = {
            'email': 'owner@example.com',
            'first_name': 'Will',
            'last_name': 'Owner',
            'password': 'Strong-password-123!',
            'account_status': User.AccountStatus.ACTIVE,
            'email_verified': True,
            'role': User.Role.OWNER,
        }
        values.update(overrides)
        password = values.pop('password')
        return User.objects.create_user(password=password, **values)

    def auth_headers(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken
        token = str(RefreshToken.for_user(user).access_token)
        return {'HTTP_AUTHORIZATION': f'Bearer {token}'}

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_owner_can_create_beneficiary_and_invitation(self):
        owner = self.active_user()
        will = Will.objects.create(owner=owner, title='Test Will', content={'body': 'test'})

        response = self.client.post(
            reverse('beneficiaries:will-beneficiaries', args=[will.pk]),
            {'recipient_email': 'mary@example.com', 'relationship_type': 'PRIMARY', 'full_name': 'Mary Doe'},
            format='json',
            **self.auth_headers(owner),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['data']['recipient_email'], 'mary@example.com')
        self.assertTrue(WillBeneficiary.objects.filter(will=will, normalized_email='mary@example.com').exists())
        self.assertTrue(BeneficiaryInvitation.objects.filter(relationship__will=will, recipient_email='mary@example.com').exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['mary@example.com'])
        self.assertIn('/beneficiary-invitation?token=', mail.outbox[0].body)

    def test_finalized_will_rejects_beneficiary_mutation(self):
        owner = self.active_user(email='owner2@example.com')
        will = Will.objects.create(owner=owner, title='Finalized Will', content={'body': 'test'}, status=Will.Status.FINALIZED)

        response = self.client.post(
            reverse('beneficiaries:will-beneficiaries', args=[will.pk]),
            {'recipient_email': 'jane@example.com', 'relationship_type': 'PRIMARY', 'full_name': 'Jane Doe'},
            format='json',
            **self.auth_headers(owner),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_archived_will_rejects_beneficiary_creation(self):
        owner = self.active_user(email='owner-archived-create@example.com')
        will = Will.objects.create(
            owner=owner,
            title='Archived Will',
            content={'body': 'test'},
            status=Will.Status.ARCHIVED,
        )

        response = self.client.post(
            reverse('beneficiaries:will-beneficiaries', args=[will.pk]),
            {'recipient_email': 'archived-create@example.com', 'relationship_type': 'PRIMARY'},
            format='json',
            **self.auth_headers(owner),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(WillBeneficiary.objects.filter(will=will).exists())

    def test_archived_will_rejects_beneficiary_update(self):
        owner = self.active_user(email='owner-archived-update@example.com')
        will = Will.objects.create(
            owner=owner,
            title='Archived Will',
            content={'body': 'test'},
            status=Will.Status.ARCHIVED,
        )
        relationship = WillBeneficiary.objects.create(
            will=will,
            normalized_email='archived-update@example.com',
            relationship_type='PRIMARY',
            full_name='Original Name',
        )

        response = self.client.patch(
            reverse('beneficiaries:will-beneficiary-detail', args=[will.pk, relationship.pk]),
            {'full_name': 'Changed Name'},
            format='json',
            **self.auth_headers(owner),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        relationship.refresh_from_db()
        self.assertEqual(relationship.full_name, 'Original Name')

    def test_archived_will_rejects_beneficiary_revocation(self):
        owner = self.active_user(email='owner-archived-revoke@example.com')
        will = Will.objects.create(
            owner=owner,
            title='Archived Will',
            content={'body': 'test'},
            status=Will.Status.ARCHIVED,
        )
        relationship = WillBeneficiary.objects.create(
            will=will,
            normalized_email='archived-revoke@example.com',
            relationship_type='PRIMARY',
        )

        response = self.client.delete(
            reverse('beneficiaries:will-beneficiary-detail', args=[will.pk, relationship.pk]),
            **self.auth_headers(owner),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        relationship.refresh_from_db()
        self.assertEqual(relationship.status, WillBeneficiary.Status.PENDING)

    def test_archived_will_rejects_invitation_resend(self):
        owner = self.active_user(email='owner-archived-resend@example.com')
        will = Will.objects.create(
            owner=owner,
            title='Archived Will',
            content={'body': 'test'},
            status=Will.Status.ARCHIVED,
        )
        relationship = WillBeneficiary.objects.create(
            will=will,
            normalized_email='archived-resend@example.com',
            relationship_type='PRIMARY',
        )

        response = self.client.post(
            reverse('beneficiaries:resend-beneficiary-invitation', args=[will.pk, relationship.pk]),
            **self.auth_headers(owner),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(BeneficiaryInvitation.objects.filter(relationship=relationship).exists())

    def test_archived_will_rejects_invitation_acceptance(self):
        owner = self.active_user(email='owner-archived-accept@example.com')
        recipient = self.active_user(email='archived-accept@example.com', role=User.Role.MEMBER)
        will = Will.objects.create(
            owner=owner,
            title='Archived Will',
            content={'body': 'test'},
            status=Will.Status.ARCHIVED,
        )
        relationship = WillBeneficiary.objects.create(
            will=will,
            normalized_email=recipient.email,
            relationship_type='PRIMARY',
        )
        invitation = BeneficiaryInvitation.objects.create(
            relationship=relationship,
            recipient_email=recipient.email,
            inviter=owner,
        )
        invitation.set_token('archived-accept-token')

        response = self.client.post(
            reverse('beneficiaries:accept-invitation'),
            {'token': 'archived-accept-token'},
            format='json',
            **self.auth_headers(recipient),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        relationship.refresh_from_db()
        invitation.refresh_from_db()
        self.assertEqual(relationship.status, WillBeneficiary.Status.PENDING)
        self.assertEqual(invitation.status, BeneficiaryInvitation.Status.PENDING)

    def test_non_owner_cannot_access_other_owner_beneficiaries(self):
        owner = self.active_user(email='owner3@example.com')
        other = self.active_user(email='owner4@example.com')
        will = Will.objects.create(owner=owner, title='Owner Will', content={'body': 'test'})
        relationship = WillBeneficiary.objects.create(will=will, normalized_email='alice@example.com', relationship_type='PRIMARY')

        response = self.client.get(
            reverse('beneficiaries:will-beneficiary-detail', args=[will.pk, relationship.pk]),
            **self.auth_headers(other),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_witness_role_cannot_manage_beneficiaries_even_for_owned_will(self):
        witness = self.active_user(email='witness-beneficiaries@example.com', role=User.Role.WITNESS)
        will = Will.objects.create(owner=witness, title='Will', content={'body': 'test'})

        response = self.client.get(
            reverse('beneficiaries:will-beneficiaries', args=[will.pk]),
            **self.auth_headers(witness),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invitation_preview_masks_recipient_and_exposes_no_will_id(self):
        owner = self.active_user(email='owner-masked-preview@example.com')
        recipient = self.active_user(email='private.recipient@example.com', role=User.Role.MEMBER)
        will = Will.objects.create(owner=owner, title='Private Will', content={'body': 'private'})
        relationship = WillBeneficiary.objects.create(will=will, normalized_email=recipient.email)
        invitation = BeneficiaryInvitation.objects.create(relationship=relationship, recipient_email=recipient.email)
        invitation.set_token('masked-preview-token')

        response = self.client.get(
            reverse('beneficiaries:beneficiary-invitation-preview', args=['masked-preview-token']),
            **self.auth_headers(recipient),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['recipient_email'], 'p***@example.com')
        self.assertNotIn('will', response.data)
        self.assertNotIn('id', response.data)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_module_three_audit_failure_rolls_back_relationship_and_sends_no_email(self):
        owner = self.active_user(email='owner-audit-failure@example.com')
        will = Will.objects.create(owner=owner, title='Will', content={'body': 'test'})

        with patch('apps.beneficiaries.views.record_beneficiary_audit', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    reverse('beneficiaries:will-beneficiaries', args=[will.pk]),
                    {'recipient_email': 'audit-recipient@example.com'},
                    format='json',
                    **self.auth_headers(owner),
                )

        self.assertFalse(WillBeneficiary.objects.filter(will=will).exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_invitation_accept_activates_relationship_for_matching_user(self):
        owner = self.active_user(email='owner5@example.com')
        recipient = self.active_user(email='mary@example.com', role=User.Role.BENEFICIARY)
        will = Will.objects.create(owner=owner, title='Will', content={'body': 'test'})
        relationship = WillBeneficiary.objects.create(will=will, beneficiary_user=recipient, normalized_email='mary@example.com', relationship_type='PRIMARY')
        invitation = BeneficiaryInvitation.objects.create(relationship=relationship, recipient_email='mary@example.com')
        invitation.set_token('abc123token')

        response = self.client.post(
            reverse('beneficiaries:accept-invitation'),
            {'token': 'abc123token'},
            format='json',
            **self.auth_headers(recipient),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        relationship.refresh_from_db()
        self.assertEqual(relationship.status, WillBeneficiary.Status.ACTIVE)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, BeneficiaryInvitation.Status.ACCEPTED)
        self.assertIsNone(invitation.token_hash)

    def test_invitation_accept_rejects_different_account(self):
        owner = self.active_user(email='owner6@example.com')
        recipient = self.active_user(email='mary2@example.com', role=User.Role.BENEFICIARY)
        other = self.active_user(email='other2@example.com', role=User.Role.BENEFICIARY)
        will = Will.objects.create(owner=owner, title='Will', content={'body': 'test'})
        relationship = WillBeneficiary.objects.create(will=will, normalized_email=recipient.email, relationship_type='PRIMARY')
        invitation = BeneficiaryInvitation.objects.create(relationship=relationship, recipient_email=recipient.email, inviter=owner)
        invitation.set_token('different-account-token')

        response = self.client.post(
            reverse('beneficiaries:accept-invitation'),
            {'token': 'different-account-token'},
            format='json',
            **self.auth_headers(other),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        relationship.refresh_from_db()
        self.assertEqual(relationship.status, WillBeneficiary.Status.PENDING)

    def test_expired_invitation_is_rejected(self):
        owner = self.active_user(email='owner7@example.com')
        recipient = self.active_user(email='expired@example.com', role=User.Role.BENEFICIARY)
        will = Will.objects.create(owner=owner, title='Will', content={'body': 'test'})
        relationship = WillBeneficiary.objects.create(will=will, normalized_email=recipient.email, relationship_type='PRIMARY')
        invitation = BeneficiaryInvitation.objects.create(
            relationship=relationship,
            recipient_email=recipient.email,
            inviter=owner,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        invitation.set_token('expired-token')

        response = self.client.post(
            reverse('beneficiaries:accept-invitation'),
            {'token': 'expired-token'},
            format='json',
            **self.auth_headers(recipient),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_expired_invitation_preview_is_not_found(self):
        owner = self.active_user(email='owner-expired-preview@example.com')
        will = Will.objects.create(owner=owner, title='Will', content={'body': 'test'})
        relationship = WillBeneficiary.objects.create(
            will=will,
            normalized_email='expired-preview@example.com',
            relationship_type='PRIMARY',
        )
        invitation = BeneficiaryInvitation.objects.create(
            relationship=relationship,
            recipient_email='expired-preview@example.com',
            inviter=owner,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        invitation.set_token('expired-preview-token')

        response = self.client.get(
            reverse('beneficiaries:beneficiary-invitation-preview', args=['expired-preview-token']),
            **self.auth_headers(owner),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_accepted_invitation_preview_is_not_found(self):
        owner = self.active_user(email='owner-used-preview@example.com')
        recipient = self.active_user(email='used-preview@example.com', role=User.Role.BENEFICIARY)
        will = Will.objects.create(owner=owner, title='Will', content={'body': 'test'})
        relationship = WillBeneficiary.objects.create(
            will=will,
            beneficiary_user=recipient,
            normalized_email=recipient.email,
            relationship_type='PRIMARY',
            status=WillBeneficiary.Status.ACTIVE,
        )
        invitation = BeneficiaryInvitation.objects.create(
            relationship=relationship,
            recipient_email=recipient.email,
            inviter=owner,
            status=BeneficiaryInvitation.Status.ACCEPTED,
        )
        invitation.set_token('accepted-preview-token')

        response = self.client.get(
            reverse('beneficiaries:beneficiary-invitation-preview', args=['accepted-preview-token']),
            **self.auth_headers(recipient),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_wrong_account_cannot_preview_invitation(self):
        owner = self.active_user(email='owner-mismatch-preview@example.com')
        recipient = self.active_user(email='preview-recipient@example.com', role=User.Role.BENEFICIARY)
        other = self.active_user(email='preview-other@example.com', role=User.Role.BENEFICIARY)
        will = Will.objects.create(owner=owner, title='Will', content={'body': 'test'})
        relationship = WillBeneficiary.objects.create(
            will=will,
            normalized_email=recipient.email,
            relationship_type='PRIMARY',
        )
        invitation = BeneficiaryInvitation.objects.create(
            relationship=relationship,
            recipient_email=recipient.email,
            inviter=owner,
        )
        invitation.set_token('recipient-bound-preview-token')

        response = self.client.get(
            reverse('beneficiaries:beneficiary-invitation-preview', args=['recipient-bound-preview-token']),
            **self.auth_headers(other),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_invited_registration_creates_unverified_member_without_accepting_invitation(self):
        owner = self.active_user(email='owner-register-beneficiary@example.com')
        will = Will.objects.create(owner=owner, title='Will', content={'body': 'test'})
        relationship = WillBeneficiary.objects.create(
            will=will,
            normalized_email='new-beneficiary@example.com',
            relationship_type='PRIMARY',
        )
        invitation = BeneficiaryInvitation.objects.create(
            relationship=relationship,
            recipient_email=relationship.normalized_email,
            inviter=owner,
        )
        invitation.set_token('new-beneficiary-registration-token')

        response = self.client.post(
            reverse('beneficiaries:register-from-invitation'),
            {
                'email': relationship.normalized_email,
                'first_name': 'New',
                'last_name': 'Beneficiary',
                'password': 'Strong-password-123!',
                'password_confirmation': 'Strong-password-123!',
                'invitation_token': 'new-beneficiary-registration-token',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email=relationship.normalized_email)
        self.assertEqual(user.role, User.Role.MEMBER)
        self.assertEqual(user.account_status, User.AccountStatus.PENDING_VERIFICATION)
        self.assertFalse(user.email_verified)
        relationship.refresh_from_db()
        invitation.refresh_from_db()
        self.assertEqual(relationship.status, WillBeneficiary.Status.PENDING)
        self.assertEqual(invitation.status, BeneficiaryInvitation.Status.PENDING)
        self.assertNotIn('new-beneficiary-registration-token', str(response.data))

    def test_invited_registration_rejects_nonmatching_email(self):
        owner = self.active_user(email='owner-register-mismatch@example.com')
        will = Will.objects.create(owner=owner, title='Will', content={'body': 'test'})
        relationship = WillBeneficiary.objects.create(
            will=will,
            normalized_email='intended-beneficiary@example.com',
            relationship_type='PRIMARY',
        )
        invitation = BeneficiaryInvitation.objects.create(
            relationship=relationship,
            recipient_email=relationship.normalized_email,
            inviter=owner,
        )
        invitation.set_token('mismatched-registration-token')

        response = self.client.post(
            reverse('beneficiaries:register-from-invitation'),
            {
                'email': 'different@example.com',
                'first_name': 'Different',
                'last_name': 'Person',
                'password': 'Strong-password-123!',
                'password_confirmation': 'Strong-password-123!',
                'invitation_token': 'mismatched-registration-token',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email='different@example.com').exists())

    def test_reused_invitation_is_rejected(self):
        owner = self.active_user(email='owner8@example.com')
        recipient = self.active_user(email='reused@example.com', role=User.Role.BENEFICIARY)
        will = Will.objects.create(owner=owner, title='Will', content={'body': 'test'})
        relationship = WillBeneficiary.objects.create(will=will, normalized_email=recipient.email, relationship_type='PRIMARY')
        invitation = BeneficiaryInvitation.objects.create(relationship=relationship, recipient_email=recipient.email, inviter=owner)
        invitation.set_token('reused-token')

        first_response = self.client.post(
            reverse('beneficiaries:accept-invitation'),
            {'token': 'reused-token'},
            format='json',
            **self.auth_headers(recipient),
        )
        second_response = self.client.post(
            reverse('beneficiaries:accept-invitation'),
            {'token': 'reused-token'},
            format='json',
            **self.auth_headers(recipient),
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_finalized_will_rejects_invitation_acceptance(self):
        owner = self.active_user(email='owner9@example.com')
        recipient = self.active_user(email='finalized@example.com', role=User.Role.BENEFICIARY)
        will = Will.objects.create(owner=owner, title='Finalized Will', content={'body': 'test'}, status=Will.Status.FINALIZED)
        relationship = WillBeneficiary.objects.create(will=will, normalized_email=recipient.email, relationship_type='PRIMARY')
        invitation = BeneficiaryInvitation.objects.create(relationship=relationship, recipient_email=recipient.email, inviter=owner)
        invitation.set_token('finalized-token')

        response = self.client.post(
            reverse('beneficiaries:accept-invitation'),
            {'token': 'finalized-token'},
            format='json',
            **self.auth_headers(recipient),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_can_revoke_beneficiary_and_invalidate_pending_invitation(self):
        owner = self.active_user(email='owner10@example.com')
        recipient = self.active_user(email='revoked@example.com', role=User.Role.BENEFICIARY)
        will = Will.objects.create(owner=owner, title='Will', content={'body': 'test'})
        relationship = WillBeneficiary.objects.create(will=will, normalized_email=recipient.email, relationship_type='PRIMARY')
        invitation = BeneficiaryInvitation.objects.create(relationship=relationship, recipient_email=recipient.email, inviter=owner)
        invitation.set_token('revoke-token')

        response = self.client.delete(
            reverse('beneficiaries:will-beneficiary-detail', args=[will.pk, relationship.pk]),
            **self.auth_headers(owner),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        relationship.refresh_from_db()
        invitation.refresh_from_db()
        self.assertEqual(relationship.status, WillBeneficiary.Status.REVOKED)
        self.assertEqual(invitation.status, BeneficiaryInvitation.Status.REVOKED)
        self.assertIsNone(invitation.token_hash)
        self.assertTrue(AuditEvent.objects.filter(details__event='beneficiary_revoked').exists())

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_owner_can_resend_invitation_rotating_token_and_preserving_history(self):
        owner = self.active_user(email='owner-resend@example.com')
        will = Will.objects.create(owner=owner, title='Will', content={'body': 'test'})
        relationship = WillBeneficiary.objects.create(
            will=will,
            normalized_email='resend-recipient@example.com',
            relationship_type='PRIMARY',
        )
        previous_invitation = BeneficiaryInvitation.objects.create(
            relationship=relationship,
            recipient_email=relationship.normalized_email,
            inviter=owner,
        )
        previous_invitation.set_token('previous-resend-token')

        response = self.client.post(
            reverse('beneficiaries:resend-beneficiary-invitation', args=[will.pk, relationship.pk]),
            **self.auth_headers(owner),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        previous_invitation.refresh_from_db()
        self.assertEqual(previous_invitation.status, BeneficiaryInvitation.Status.REVOKED)
        self.assertEqual(BeneficiaryInvitation.objects.filter(relationship=relationship).count(), 2)
        current_invitation = BeneficiaryInvitation.objects.filter(relationship=relationship).exclude(pk=previous_invitation.pk).get()
        self.assertEqual(current_invitation.status, BeneficiaryInvitation.Status.PENDING)
        self.assertEqual(current_invitation.inviter, owner)
        self.assertNotEqual(current_invitation.token_hash, previous_invitation.token_hash)
        self.assertGreater(current_invitation.expires_at, timezone.now())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [relationship.normalized_email])
        self.assertIn('/beneficiary-invitation?token=', mail.outbox[0].body)
        sent_token = parse_qs(urlsplit(mail.outbox[0].body.split('Invitation link: ', 1)[1].splitlines()[0]).query)['token'][0]
        self.assertEqual(current_invitation.token_hash, BeneficiaryInvitation.hash_token(sent_token))
        self.assertNotIn(sent_token, str(response.data))
        self.assertTrue(AuditEvent.objects.filter(details__event='beneficiary_invitation_resent').exists())

    def test_non_owner_cannot_resend_beneficiary_invitation(self):
        owner = self.active_user(email='owner-resend-auth@example.com')
        other = self.active_user(email='other-resend-auth@example.com')
        will = Will.objects.create(owner=owner, title='Will', content={'body': 'test'})
        relationship = WillBeneficiary.objects.create(
            will=will,
            normalized_email='resend-auth@example.com',
            relationship_type='PRIMARY',
        )

        response = self.client.post(
            reverse('beneficiaries:resend-beneficiary-invitation', args=[will.pk, relationship.pk]),
            **self.auth_headers(other),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(BeneficiaryInvitation.objects.filter(relationship=relationship).exists())

    def test_finalized_will_rejects_invitation_resend(self):
        owner = self.active_user(email='owner-resend-finalized@example.com')
        will = Will.objects.create(
            owner=owner,
            title='Finalized Will',
            content={'body': 'test'},
            status=Will.Status.FINALIZED,
        )
        relationship = WillBeneficiary.objects.create(
            will=will,
            normalized_email='resend-finalized@example.com',
            relationship_type='PRIMARY',
        )

        response = self.client.post(
            reverse('beneficiaries:resend-beneficiary-invitation', args=[will.pk, relationship.pk]),
            **self.auth_headers(owner),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(BeneficiaryInvitation.objects.filter(relationship=relationship).exists())

    def test_beneficiary_self_list_excludes_revoked_relationships(self):
        owner = self.active_user(email='owner-self-list@example.com')
        beneficiary = self.active_user(email='self-list@example.com', role=User.Role.BENEFICIARY)
        active_will = Will.objects.create(owner=owner, title='Active Will', content={'body': 'test'})
        revoked_will = Will.objects.create(owner=owner, title='Revoked Will', content={'body': 'test'})
        active_relationship = WillBeneficiary.objects.create(
            will=active_will,
            beneficiary_user=beneficiary,
            normalized_email=beneficiary.email,
            relationship_type='PRIMARY',
            status=WillBeneficiary.Status.ACTIVE,
        )
        WillBeneficiary.objects.create(
            will=revoked_will,
            beneficiary_user=beneficiary,
            normalized_email=beneficiary.email,
            relationship_type='PRIMARY',
            status=WillBeneficiary.Status.REVOKED,
        )

        response = self.client.get(
            reverse('beneficiaries:my-beneficiary-relationships'),
            **self.auth_headers(beneficiary),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item['id'] for item in response.data['data']], [active_relationship.pk])

    def test_member_can_be_beneficiary_without_access_to_owners_will(self):
        owner = self.active_user(email='relationship-owner@example.com')
        member = self.active_user(email='member-beneficiary@example.com', role=User.Role.MEMBER)
        will = Will.objects.create(owner=owner, title='Private Owner Will', content={'body': 'private'})
        WillBeneficiary.objects.create(
            will=will,
            beneficiary_user=member,
            normalized_email=member.email,
            relationship_type='PRIMARY',
            status=WillBeneficiary.Status.ACTIVE,
        )

        relationships_response = self.client.get(
            reverse('beneficiaries:my-beneficiary-relationships'),
            **self.auth_headers(member),
        )
        will_response = self.client.get(
            reverse('wills:will-detail', args=[will.pk]),
            **self.auth_headers(member),
        )

        self.assertEqual(relationships_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(relationships_response.data['data']), 1)
        self.assertEqual(will_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_matching_user_can_decline_invitation(self):
        owner = self.active_user(email='owner11@example.com')
        recipient = self.active_user(email='decline@example.com', role=User.Role.BENEFICIARY)
        will = Will.objects.create(owner=owner, title='Will', content={'body': 'test'})
        relationship = WillBeneficiary.objects.create(will=will, normalized_email=recipient.email, relationship_type='PRIMARY')
        invitation = BeneficiaryInvitation.objects.create(relationship=relationship, recipient_email=recipient.email, inviter=owner)
        invitation.set_token('decline-token')

        response = self.client.post(
            reverse('beneficiaries:decline-invitation'),
            {'token': 'decline-token'},
            format='json',
            **self.auth_headers(recipient),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        relationship.refresh_from_db()
        invitation.refresh_from_db()
        self.assertEqual(relationship.status, WillBeneficiary.Status.DECLINED)
        self.assertEqual(invitation.status, BeneficiaryInvitation.Status.DECLINED)
        self.assertIsNone(invitation.token_hash)
        self.assertTrue(AuditEvent.objects.filter(details__event='beneficiary_invitation_declined').exists())

    def test_decline_rejects_different_account(self):
        owner = self.active_user(email='owner11@example.com')
        recipient = self.active_user(email='decline2@example.com', role=User.Role.BENEFICIARY)
        other = self.active_user(email='other3@example.com', role=User.Role.BENEFICIARY)
        will = Will.objects.create(owner=owner, title='Will', content={'body': 'test'})
        relationship = WillBeneficiary.objects.create(will=will, normalized_email=recipient.email, relationship_type='PRIMARY')
        invitation = BeneficiaryInvitation.objects.create(relationship=relationship, recipient_email=recipient.email, inviter=owner)
        invitation.set_token('decline-mismatch-token')

        response = self.client.post(
            reverse('beneficiaries:decline-invitation'),
            {'token': 'decline-mismatch-token'},
            format='json',
            **self.auth_headers(other),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        relationship.refresh_from_db()
        self.assertEqual(relationship.status, WillBeneficiary.Status.PENDING)

    def test_declined_invitation_cannot_be_reused(self):
        owner = self.active_user(email='owner12@example.com')
        recipient = self.active_user(email='decline3@example.com', role=User.Role.BENEFICIARY)
        will = Will.objects.create(owner=owner, title='Will', content={'body': 'test'})
        relationship = WillBeneficiary.objects.create(will=will, normalized_email=recipient.email, relationship_type='PRIMARY')
        invitation = BeneficiaryInvitation.objects.create(relationship=relationship, recipient_email=recipient.email, inviter=owner)
        invitation.set_token('decline-replay-token')

        first_response = self.client.post(
            reverse('beneficiaries:decline-invitation'),
            {'token': 'decline-replay-token'},
            format='json',
            **self.auth_headers(recipient),
        )
        second_response = self.client.post(
            reverse('beneficiaries:decline-invitation'),
            {'token': 'decline-replay-token'},
            format='json',
            **self.auth_headers(recipient),
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_declined_relationship_cannot_be_edited_or_revoked(self):
        owner = self.active_user(email='owner-declined-history@example.com')
        will = Will.objects.create(owner=owner, title='Will', content={'body': 'test'})
        relationship = WillBeneficiary.objects.create(
            will=will,
            normalized_email='declined-history@example.com',
            status=WillBeneficiary.Status.DECLINED,
        )
        detail_url = reverse('beneficiaries:will-beneficiary-detail', args=[will.pk, relationship.pk])

        update_response = self.client.patch(
            detail_url,
            {'full_name': 'Changed'},
            format='json',
            **self.auth_headers(owner),
        )
        revoke_response = self.client.delete(detail_url, **self.auth_headers(owner))

        self.assertEqual(update_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(revoke_response.status_code, status.HTTP_400_BAD_REQUEST)
        relationship.refresh_from_db()
        self.assertEqual(relationship.status, WillBeneficiary.Status.DECLINED)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_owner_can_reinvite_recipient_after_declined_relationship(self):
        owner = self.active_user(email='owner-reinvite@example.com')
        will = Will.objects.create(owner=owner, title='Will', content={'body': 'test'})
        WillBeneficiary.objects.create(
            will=will,
            normalized_email='reinvite-recipient@example.com',
            status=WillBeneficiary.Status.DECLINED,
        )

        response = self.client.post(
            reverse('beneficiaries:will-beneficiaries', args=[will.pk]),
            {'recipient_email': 'REINVITE-RECIPIENT@example.com', 'relationship_type': 'PRIMARY'},
            format='json',
            **self.auth_headers(owner),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            WillBeneficiary.objects.filter(will=will, normalized_email='reinvite-recipient@example.com').count(),
            2,
        )

from django.db.models import ProtectedError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from .models import Will


class WillManagementApiTests(APITestCase):
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
        login_response = self.client.post(
            reverse('accounts:login'),
            {'email': user.email, 'password': 'Strong-password-123!'},
            format='json',
        )
        return {'HTTP_AUTHORIZATION': f"Bearer {login_response.data['data']['access']}"}

    def test_owner_can_create_will(self):
        owner = self.active_user(email='owner1@example.com')
        response = self.client.post(
            reverse('wills:will-list'),
            {'title': 'Final Will', 'content': {'sections': [{'title': 'Assets', 'body': 'House and land'}]}},
            format='json',
            **self.auth_headers(owner),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Will.objects.filter(owner=owner).count(), 1)
        self.assertEqual(Will.objects.get(owner=owner).status, Will.Status.DRAFT)
        self.assertTrue(
            AuditEvent.objects.filter(
                event_type=AuditEvent.EventType.WILL_CREATED,
                actor=owner,
            ).exists()
        )

    def test_member_can_create_and_list_only_their_own_wills(self):
        member = self.active_user(email='member-owner@example.com', role=User.Role.MEMBER)
        other_owner = self.active_user(email='other-owner@example.com')
        other_will = Will.objects.create(owner=other_owner, title='Private Will', content={'body': 'private'})
        headers = self.auth_headers(member)

        create_response = self.client.post(
            reverse('wills:will-list'),
            {'title': 'Member Will', 'content': {'body': 'member private'}},
            format='json',
            **headers,
        )
        list_response = self.client.get(reverse('wills:will-list'), **headers)
        other_detail_response = self.client.get(
            reverse('wills:will-detail', args=[other_will.pk]),
            **headers,
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data['data']), 1)
        self.assertEqual(list_response.data['data'][0]['owner'], member.pk)
        self.assertEqual(other_detail_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_member_cannot_use_legacy_generic_invitation_api(self):
        member = self.active_user(email='member-legacy-invite@example.com', role=User.Role.MEMBER)

        response = self.client.post(
            reverse('accounts:invitations'),
            {'email': 'collaborator@example.com', 'role': 'WITNESS'},
            format='json',
            **self.auth_headers(member),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_save_structured_will_content(self):
        owner = self.active_user(email='structured-owner@example.com')
        response = self.client.post(
            reverse('wills:will-list'),
            {
                'title': 'Structured Will',
                'content': {
                    'testator': {'full_name': 'Will Owner', 'marital_status': 'SINGLE'},
                    'family': {'children': []},
                    'executor': {'full_name': 'Trusted Executor'},
                    'beneficiaries': [{'full_name': 'Named Beneficiary'}],
                    'gifts': [{'description': 'Family land', 'beneficiary_name': 'Named Beneficiary'}],
                    'residual_estate': 'Everything else goes to the named beneficiary.',
                },
            },
            format='json',
            **self.auth_headers(owner),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_will_content_rejects_invalid_section_shapes(self):
        owner = self.active_user(email='invalid-structure@example.com')
        response = self.client.post(
            reverse('wills:will-list'),
            {'title': 'Invalid Will', 'content': {'beneficiaries': 'not-a-list'}},
            format='json',
            **self.auth_headers(owner),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_content_exceeding_100kb_rejected(self):
        owner = self.active_user(email='large-payload@example.com')
        # 200 KB payload in residual_estate text section
        large_payload = {'residual_estate': 'X' * (200 * 1024)}
        response = self.client.post(
            reverse('wills:will-list'),
            {'title': 'Oversized Will', 'content': large_payload},
            format='json',
            **self.auth_headers(owner),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Content size exceeds maximum allowed limit', str(response.data))

    def test_content_nested_deeper_than_10_levels_rejected(self):
        owner = self.active_user(email='deep-nested@example.com')
        # Build 11-level deep dictionary
        nested = {'leaf': 'value'}
        for _ in range(10):
            nested = {'level': nested}
        response = self.client.post(
            reverse('wills:will-list'),
            {'title': 'Deeply Nested Will', 'content': nested},
            format='json',
            **self.auth_headers(owner),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Content structure cannot be nested deeper than 10 levels', str(response.data))

    def test_title_exceeding_200_chars_rejected(self):
        owner = self.active_user(email='long-title@example.com')
        long_title = 'A' * 201
        response = self.client.post(
            reverse('wills:will-list'),
            {'title': long_title, 'content': {}},
            format='json',
            **self.auth_headers(owner),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_or_whitespace_title_rejected(self):
        owner = self.active_user(email='blank-title@example.com')
        response = self.client.post(
            reverse('wills:will-list'),
            {'title': '   ', 'content': {'testator': {'full_name': 'Test'}}},
            format='json',
            **self.auth_headers(owner),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_user_cannot_access_wills(self):
        response = self.client.get(reverse('wills:will-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        response_create = self.client.post(
            reverse('wills:will-list'),
            {'title': 'Will'},
            format='json',
        )
        self.assertEqual(response_create.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_or_expired_jwt_rejected(self):
        # Malformed JWT token
        bad_headers = {'HTTP_AUTHORIZATION': 'Bearer invalid.token.payload'}
        response = self.client.get(reverse('wills:will-list'), **bad_headers)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_owner_can_retrieve_own_will(self):
        owner = self.active_user(email='owner2@example.com')
        will = Will.objects.create(owner=owner, title='My Will', content={'body': 'test'})
        response = self.client.get(reverse('wills:will-detail', args=[will.pk]), **self.auth_headers(owner))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['owner_email'], owner.email)
        self.assertTrue(AuditEvent.objects.filter(event_type=AuditEvent.EventType.WILL_ACCESSED).exists())

    def test_owner_update_increments_version(self):
        owner = self.active_user(email='owner-version@example.com')
        will = Will.objects.create(owner=owner, title='My Will', content={'body': 'old'})
        response = self.client.patch(
            reverse('wills:will-detail', args=[will.pk]),
            {'content': {'body': 'new'}},
            format='json',
            **self.auth_headers(owner),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        will.refresh_from_db()
        self.assertEqual(will.version, 2)
        self.assertTrue(AuditEvent.objects.filter(event_type=AuditEvent.EventType.WILL_UPDATED).exists())

    def test_idor_get_anti_enumeration_returns_404_and_logs_audit(self):
        owner_a = self.active_user(email='ownera@example.com')
        owner_b = self.active_user(email='ownerb@example.com')
        will_a = Will.objects.create(owner=owner_a, title='Owner A Will', content={'body': 'secret'})

        response = self.client.get(reverse('wills:will-detail', args=[will_a.pk]), **self.auth_headers(owner_b))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(
            AuditEvent.objects.filter(
                event_type=AuditEvent.EventType.WILL_ACCESS_DENIED,
                actor=owner_b,
            ).exists()
        )

    def test_idor_patch_rejected(self):
        owner_a = self.active_user(email='ownera_patch@example.com')
        owner_b = self.active_user(email='ownerb_patch@example.com')
        will_a = Will.objects.create(owner=owner_a, title='Original Title', content={'body': 'secret'})

        response = self.client.patch(
            reverse('wills:will-detail', args=[will_a.pk]),
            {'title': 'Hacked Title'},
            format='json',
            **self.auth_headers(owner_b),
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        will_a.refresh_from_db()
        self.assertEqual(will_a.title, 'Original Title')

    def test_idor_put_rejected(self):
        owner_a = self.active_user(email='ownera_put@example.com')
        owner_b = self.active_user(email='ownerb_put@example.com')
        will_a = Will.objects.create(owner=owner_a, title='Original Title', content={'body': 'secret'})

        response = self.client.put(
            reverse('wills:will-detail', args=[will_a.pk]),
            {'title': 'Replaced Title', 'content': {}},
            format='json',
            **self.auth_headers(owner_b),
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        will_a.refresh_from_db()
        self.assertEqual(will_a.title, 'Original Title')

    def test_idor_delete_rejected(self):
        owner_a = self.active_user(email='ownera_del@example.com')
        owner_b = self.active_user(email='ownerb_del@example.com')
        will_a = Will.objects.create(owner=owner_a, title='Owner A Will', content={'body': 'secret'})

        response = self.client.delete(reverse('wills:will-detail', args=[will_a.pk]), **self.auth_headers(owner_b))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Will.objects.filter(pk=will_a.pk).exists())

    def test_idor_finalize_rejected(self):
        owner_a = self.active_user(email='ownera_fin@example.com')
        owner_b = self.active_user(email='ownerb_fin@example.com')
        will_a = Will.objects.create(owner=owner_a, title='Owner A Will', content={'body': 'secret'})

        response = self.client.post(reverse('wills:will-finalize', args=[will_a.pk]), **self.auth_headers(owner_b))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        will_a.refresh_from_db()
        self.assertEqual(will_a.status, Will.Status.DRAFT)

    def test_mass_assignment_owner_tampering_ignored(self):
        owner_a = self.active_user(email='victim_owner@example.com')
        attacker = self.active_user(email='attacker_owner@example.com')

        response = self.client.post(
            reverse('wills:will-list'),
            {'title': 'Spoofed Will', 'owner': owner_a.pk, 'content': {}},
            format='json',
            **self.auth_headers(attacker),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_will = Will.objects.get(title='Spoofed Will')
        self.assertEqual(created_will.owner, attacker)

    def test_mass_assignment_status_and_metadata_tampering_ignored(self):
        owner = self.active_user(email='metadata_owner@example.com')
        response = self.client.post(
            reverse('wills:will-list'),
            {
                'title': 'Tamper Status Will',
                'status': Will.Status.FINALIZED,
                'version': 99,
                'finalized_at': '2020-01-01T00:00:00Z',
                'content': {},
            },
            format='json',
            **self.auth_headers(owner),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        will = Will.objects.get(title='Tamper Status Will')
        self.assertEqual(will.status, Will.Status.DRAFT)
        self.assertEqual(will.version, 1)
        self.assertIsNone(will.finalized_at)

        patch_response = self.client.patch(
            reverse('wills:will-detail', args=[will.pk]),
            {'status': Will.Status.FINALIZED, 'version': 500},
            format='json',
            **self.auth_headers(owner),
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        will.refresh_from_db()
        self.assertEqual(will.status, Will.Status.DRAFT)
        self.assertEqual(will.version, 2)

    def test_finalized_will_cannot_be_edited(self):
        owner = self.active_user(email='owner3@example.com')
        will = Will.objects.create(owner=owner, title='Will', content={'body': 'initial'})
        will.status = Will.Status.FINALIZED
        will.finalized_at = will.updated_at
        will.save()

        response = self.client.patch(
            reverse('wills:will-detail', args=[will.pk]),
            {'title': 'Changed title'},
            format='json',
            **self.auth_headers(owner),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_finalized_will_cannot_be_deleted(self):
        owner = self.active_user(email='owner_del_fin@example.com')
        will = Will.objects.create(owner=owner, title='Finalized Will', content={'body': 'initial'})
        will.status = Will.Status.FINALIZED
        will.finalized_at = will.updated_at
        will.save()

        response = self.client.delete(reverse('wills:will-detail', args=[will.pk]), **self.auth_headers(owner))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Will.objects.filter(pk=will.pk).exists())

    def test_archived_will_cannot_be_edited(self):
        owner = self.active_user(email='owner_archived_edit@example.com')
        will = Will.objects.create(owner=owner, title='Archived Will', content={'body': 'initial'}, status=Will.Status.ARCHIVED)

        response = self.client.patch(
            reverse('wills:will-detail', args=[will.pk]),
            {'title': 'Changed title', 'content': {'body': 'changed'}},
            format='json',
            **self.auth_headers(owner),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        will.refresh_from_db()
        self.assertEqual(will.title, 'Archived Will')
        self.assertEqual(will.content, {'body': 'initial'})
        self.assertEqual(will.status, Will.Status.ARCHIVED)

    def test_archived_will_cannot_be_deleted(self):
        owner = self.active_user(email='owner_archived_delete@example.com')
        will = Will.objects.create(owner=owner, title='Archived Will', content={'body': 'initial'}, status=Will.Status.ARCHIVED)

        response = self.client.delete(reverse('wills:will-detail', args=[will.pk]), **self.auth_headers(owner))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Will.objects.filter(pk=will.pk, status=Will.Status.ARCHIVED).exists())

    def test_owner_can_delete_draft_will_and_generates_audit_event(self):
        owner = self.active_user(email='owner_del_draft@example.com')
        will = Will.objects.create(owner=owner, title='Draft To Delete', content={'body': 'draft'})

        response = self.client.delete(reverse('wills:will-detail', args=[will.pk]), **self.auth_headers(owner))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Will.objects.filter(pk=will.pk).exists())
        self.assertTrue(
            AuditEvent.objects.filter(
                event_type=AuditEvent.EventType.WILL_DELETED,
                actor=owner,
            ).exists()
        )

    def test_protect_on_user_delete_prevents_cascade_will_destruction(self):
        owner = self.active_user(email='protect_owner@example.com')
        Will.objects.create(owner=owner, title='Protected Will', content={})
        with self.assertRaises(ProtectedError):
            owner.delete()

    def test_owner_can_finalize_their_will(self):
        owner = self.active_user(email='owner4@example.com')
        will = Will.objects.create(owner=owner, title='Draft Will', content={'body': 'test'})

        response = self.client.post(reverse('wills:will-finalize', args=[will.pk]), **self.auth_headers(owner))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        will.refresh_from_db()
        self.assertEqual(will.status, Will.Status.FINALIZED)
        self.assertIsNotNone(will.finalized_at)
        self.assertEqual(will.version, 2)
        self.assertTrue(AuditEvent.objects.filter(event_type=AuditEvent.EventType.WILL_FINALIZED).exists())

    def test_finalization_cannot_be_repeated(self):
        owner = self.active_user(email='owner6@example.com')
        will = Will.objects.create(owner=owner, title='Draft Will', content={'body': 'test'})
        headers = self.auth_headers(owner)

        self.client.post(reverse('wills:will-finalize', args=[will.pk]), **headers)
        response = self.client.post(reverse('wills:will-finalize', args=[will.pk]), **headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_owner_roles_cannot_list_private_wills(self):
        for role in (
            User.Role.WITNESS,
            User.Role.BENEFICIARY,
            User.Role.LAWYER_VERIFIER,
            User.Role.ADMINISTRATOR,
        ):
            user = self.active_user(email=f'{role.lower()}@example.com', role=role)
            response = self.client.get(reverse('wills:will-list'), **self.auth_headers(user))
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, role)

    def test_lawyer_cannot_access_or_manipulate_private_will(self):
        owner = self.active_user(email='owner_lawyer_test@example.com')
        lawyer = self.active_user(email='lawyer_test@example.com', role=User.Role.LAWYER_VERIFIER)
        will = Will.objects.create(owner=owner, title='Secret Will', content={'body': 'confidential'})

        headers = self.auth_headers(lawyer)
        self.assertEqual(self.client.get(reverse('wills:will-list'), **headers).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(reverse('wills:will-detail', args=[will.pk]), **headers).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.post(reverse('wills:will-list'), {'title': 'Lawyer Will'}, format='json', **headers).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.patch(reverse('wills:will-detail', args=[will.pk]), {'title': 'Tampered'}, format='json', **headers).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.post(reverse('wills:will-finalize', args=[will.pk]), **headers).status_code, status.HTTP_404_NOT_FOUND)

    def test_witness_cannot_access_or_manipulate_private_will(self):
        owner = self.active_user(email='owner_witness_test@example.com')
        witness = self.active_user(email='witness_test@example.com', role=User.Role.WITNESS)
        will = Will.objects.create(owner=owner, title='Witness Will', content={'body': 'confidential'})

        headers = self.auth_headers(witness)
        self.assertEqual(self.client.get(reverse('wills:will-list'), **headers).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(reverse('wills:will-detail', args=[will.pk]), **headers).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.patch(reverse('wills:will-detail', args=[will.pk]), {'title': 'Tampered'}, format='json', **headers).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.post(reverse('wills:will-finalize', args=[will.pk]), **headers).status_code, status.HTTP_404_NOT_FOUND)

    def test_beneficiary_cannot_access_or_manipulate_private_will(self):
        owner = self.active_user(email='owner_bene_test@example.com')
        beneficiary = self.active_user(email='beneficiary_test@example.com', role=User.Role.BENEFICIARY)
        will = Will.objects.create(owner=owner, title='Beneficiary Will', content={'body': 'confidential', 'beneficiaries': [{'full_name': 'Beneficiary'}]})

        headers = self.auth_headers(beneficiary)
        self.assertEqual(self.client.get(reverse('wills:will-list'), **headers).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(reverse('wills:will-detail', args=[will.pk]), **headers).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.patch(reverse('wills:will-detail', args=[will.pk]), {'title': 'Tampered'}, format='json', **headers).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.post(reverse('wills:will-finalize', args=[will.pk]), **headers).status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_cannot_access_private_will_content(self):
        owner = self.active_user(email='owner_admin_test@example.com')
        admin_user = self.active_user(email='admin_test@example.com', role=User.Role.ADMINISTRATOR)
        will = Will.objects.create(owner=owner, title='Private Estate Will', content={'body': 'confidential'})

        headers = self.auth_headers(admin_user)
        self.assertEqual(self.client.get(reverse('wills:will-list'), **headers).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(reverse('wills:will-detail', args=[will.pk]), **headers).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.post(reverse('wills:will-finalize', args=[will.pk]), **headers).status_code, status.HTTP_404_NOT_FOUND)

    def test_inactive_or_suspended_owner_cannot_access_wills(self):
        for status_choice in (User.AccountStatus.PENDING_VERIFICATION, User.AccountStatus.INACTIVE, User.AccountStatus.SUSPENDED):
            user = self.active_user(email=f'inactive_{status_choice.lower()}@example.com', account_status=status_choice)
            will = Will.objects.create(owner=user, title='My Will', content={})
            from rest_framework_simplejwt.tokens import RefreshToken
            token = str(RefreshToken.for_user(user).access_token)
            headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

            response = self.client.get(reverse('wills:will-list'), **headers)
            # Inactive users fail SimpleJWT authentication with 401 Unauthorized
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED, status_choice)
            response_detail = self.client.get(reverse('wills:will-detail', args=[will.pk]), **headers)
            self.assertEqual(response_detail.status_code, status.HTTP_401_UNAUTHORIZED, status_choice)

    def test_audit_event_does_not_leak_private_will_content(self):
        owner = self.active_user(email='audit_leak_test@example.com')
        sensitive_content = {'secret_assets': 'Offshore vault code 998877'}
        response = self.client.post(
            reverse('wills:will-list'),
            {'title': 'Secret Will', 'content': sensitive_content},
            format='json',
            **self.auth_headers(owner),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        events = AuditEvent.objects.filter(actor=owner)
        self.assertTrue(events.exists())
        for event in events:
            details_str = str(event.details)
            self.assertNotIn('Offshore vault', details_str)
            self.assertNotIn('secret_assets', details_str)

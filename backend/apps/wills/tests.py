from rest_framework import status
from rest_framework.test import APITestCase
from django.urls import reverse

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
        self.client.login(username=owner.email, password='Strong-password-123!')
        response = self.client.post(
            reverse('wills:will-list'),
            {'title': 'Final Will', 'content': {'sections': [{'title': 'Assets', 'body': 'House and land'}]}},
            format='json',
            **self.auth_headers(owner),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Will.objects.filter(owner=owner).count(), 1)
        self.assertEqual(Will.objects.get(owner=owner).status, Will.Status.DRAFT)

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

    def test_unauthenticated_user_cannot_list_wills(self):
        response = self.client.get(reverse('wills:will-list'))
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

    def test_cross_owner_cannot_access_will(self):
        owner_a = self.active_user(email='ownera@example.com')
        owner_b = self.active_user(email='ownerb@example.com')
        will = Will.objects.create(owner=owner_a, title='Owner A Will', content={'body': 'secret'})

        response = self.client.get(reverse('wills:will-detail', args=[will.pk]), **self.auth_headers(owner_b))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(AuditEvent.objects.filter(event_type=AuditEvent.EventType.WILL_ACCESS_DENIED).exists())

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

    def test_owner_can_finalize_their_will(self):
        owner = self.active_user(email='owner4@example.com')
        will = Will.objects.create(owner=owner, title='Draft Will', content={'body': 'test'})

        response = self.client.post(reverse('wills:will-finalize', args=[will.pk]), **self.auth_headers(owner))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        will.refresh_from_db()
        self.assertEqual(will.status, Will.Status.FINALIZED)
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

    def test_non_owner_cannot_finalize_will(self):
        owner = self.active_user(email='owner5@example.com')
        other = self.active_user(email='other5@example.com')
        will = Will.objects.create(owner=owner, title='Other Will', content={'body': 'secret'})

        response = self.client.post(reverse('wills:will-finalize', args=[will.pk]), **self.auth_headers(other))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

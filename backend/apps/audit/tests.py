from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from .models import AuditEvent


class MyActivityApiTests(APITestCase):
    def active_user(self, email):
        return User.objects.create_user(
            email=email,
            first_name='Test',
            last_name='User',
            password='Strong-password-123!',
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )

    def test_activity_is_scoped_to_actor_or_target_and_excludes_details(self):
        user = self.active_user('activity-user@example.com')
        other_user = self.active_user('other-activity-user@example.com')
        own_event = AuditEvent.objects.create(
            event_type=AuditEvent.EventType.LOGIN_SUCCESS,
            actor=user,
            details={'email': user.email, 'secret': 'must not be returned'},
        )
        targeted_event = AuditEvent.objects.create(
            event_type=AuditEvent.EventType.EMAIL_VERIFIED,
            target_user=user,
            details={'email': user.email},
        )
        AuditEvent.objects.create(
            event_type=AuditEvent.EventType.LOGIN_SUCCESS,
            actor=other_user,
            details={'email': other_user.email},
        )
        AuditEvent.objects.create(
            event_type=AuditEvent.EventType.LOGIN_FAILED,
            details={'attempted_email': user.email},
        )
        self.client.force_authenticate(user)

        response = self.client.get(reverse('audit:my-activity'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {item['id'] for item in response.data['data']}
        self.assertEqual(returned_ids, {own_event.pk, targeted_event.pk})
        self.assertTrue(all('details' not in item for item in response.data['data']))
        self.assertTrue(all('secret' not in str(item) for item in response.data['data']))

    def test_activity_requires_authentication(self):
        response = self.client.get(reverse('audit:my-activity'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_activity_is_limited_to_ten_events(self):
        user = self.active_user('activity-limit@example.com')
        for _ in range(12):
            AuditEvent.objects.create(event_type=AuditEvent.EventType.LOGIN_SUCCESS, actor=user)
        self.client.force_authenticate(user)

        response = self.client.get(reverse('audit:my-activity'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 10)

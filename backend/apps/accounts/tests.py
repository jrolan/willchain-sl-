from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import User


class AuthenticationApiTests(APITestCase):
	def active_user(self, **overrides):
		values = {
			'email': 'owner@example.com',
			'first_name': 'Will',
			'last_name': 'Owner',
			'password': 'Strong-password-123!',
			'account_status': User.AccountStatus.ACTIVE,
			'email_verified': True,
		}
		values.update(overrides)
		password = values.pop('password')
		return User.objects.create_user(password=password, **values)

	def test_registration_creates_pending_owner(self):
		response = self.client.post(
			reverse('accounts:register'),
			{
				'email': 'new@example.com',
				'first_name': 'New',
				'last_name': 'Owner',
				'password': 'Strong-password-123!',
				'password_confirmation': 'Strong-password-123!',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		user = User.objects.get(email='new@example.com')
		self.assertEqual(user.role, User.Role.OWNER)
		self.assertEqual(user.account_status, User.AccountStatus.PENDING_VERIFICATION)
		self.assertFalse(user.email_verified)

	def test_registration_cannot_choose_privileged_role(self):
		response = self.client.post(
			reverse('accounts:register'),
			{
				'email': 'lawyer@example.com',
				'first_name': 'Future',
				'last_name': 'Lawyer',
				'role': User.Role.ADMINISTRATOR,
				'password': 'Strong-password-123!',
				'password_confirmation': 'Strong-password-123!',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(User.objects.get(email='lawyer@example.com').role, User.Role.OWNER)

	def test_unverified_account_cannot_login(self):
		self.active_user(email_verified=False, account_status=User.AccountStatus.PENDING_VERIFICATION)
		response = self.client.post(
			reverse('accounts:login'),
			{'email': 'owner@example.com', 'password': 'Strong-password-123!'},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_profile_requires_authentication(self):
		response = self.client.get(reverse('accounts:me'))

		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_active_user_can_login_and_read_own_profile(self):
		self.active_user()
		login_response = self.client.post(
			reverse('accounts:login'),
			{'email': 'owner@example.com', 'password': 'Strong-password-123!'},
			format='json',
		)
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['data']['access']}")

		response = self.client.get(reverse('accounts:me'))

		self.assertEqual(login_response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['email'], 'owner@example.com')

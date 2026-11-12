import io
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
from PIL import Image

from unittest.mock import patch

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase

from apps.audit.models import AuditEvent
from apps.wills.models import Will
from .services import verify_google_id_token
from .models import Invitation, User
from .permissions import IsOwner, IsTestator


def create_test_image(format='JPEG', size=(100, 100)):
	file = io.BytesIO()
	image = Image.new('RGB', size, color=(73, 109, 137))
	image.save(file, format=format)
	file.seek(0)
	return file


class AuthenticationApiTests(APITestCase):
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

	@staticmethod
	def patch_google_token(payload):
		return patch('apps.accounts.views.verify_google_id_token', return_value=payload)

	def test_google_token_verification_fails_closed_without_google_auth(self):
		with patch('apps.accounts.services.google_id_token', None), patch(
			'apps.accounts.services.google_requests', None
		):
			with self.assertRaises(ValueError):
				verify_google_id_token('unverified-token', 'client-123')

	# --- 1. REGISTRATION TESTS ---

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
		self.assertFalse(user.is_active)
		self.assertEqual(len(mail.outbox), 1)
		self.assertIn('Verify your WillChain account', mail.outbox[0].subject)
		self.assertTrue(AuditEvent.objects.filter(event_type=AuditEvent.EventType.USER_REGISTERED).exists())

	def test_registration_rejects_duplicate_email(self):
		self.active_user(email='existing@example.com')
		response = self.client.post(
			reverse('accounts:register'),
			{
				'email': 'existing@example.com',
				'first_name': 'Duplicate',
				'last_name': 'User',
				'password': 'Strong-password-123!',
				'password_confirmation': 'Strong-password-123!',
			},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_registration_rejects_mismatched_password(self):
		response = self.client.post(
			reverse('accounts:register'),
			{
				'email': 'mismatch@example.com',
				'first_name': 'Mismatch',
				'last_name': 'User',
				'password': 'Strong-password-123!',
				'password_confirmation': 'Different-password-123!',
			},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

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

	# --- 2. LOGIN & JWT TESTS ---

	def test_active_user_can_login_and_receive_jwt(self):
		self.active_user()
		response = self.client.post(
			reverse('accounts:login'),
			{'email': 'owner@example.com', 'password': 'Strong-password-123!'},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('access', response.data['data'])
		self.assertEqual(response.data['data']['user']['email'], 'owner@example.com')
		self.assertIn('willchain_refresh', response.cookies)
		self.assertTrue(response.cookies['willchain_refresh']['httponly'])
		self.assertTrue(AuditEvent.objects.filter(event_type=AuditEvent.EventType.LOGIN_SUCCESS).exists())

	def test_login_fails_with_invalid_password(self):
		self.active_user()
		response = self.client.post(
			reverse('accounts:login'),
			{'email': 'owner@example.com', 'password': 'Wrong-password!'},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertTrue(AuditEvent.objects.filter(event_type=AuditEvent.EventType.LOGIN_FAILED).exists())

	def test_unverified_account_cannot_login(self):
		self.active_user(email_verified=False, account_status=User.AccountStatus.PENDING_VERIFICATION)
		response = self.client.post(
			reverse('accounts:login'),
			{'email': 'owner@example.com', 'password': 'Strong-password-123!'},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_suspended_account_cannot_login(self):
		self.active_user(account_status=User.AccountStatus.SUSPENDED)
		response = self.client.post(
			reverse('accounts:login'),
			{'email': 'owner@example.com', 'password': 'Strong-password-123!'},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_google_login_registers_new_owner_pending_verification_without_jwt(self):
		with self.settings(GOOGLE_OAUTH2_CLIENT_ID='client-123'):
			with self.patch_google_token(
				{'sub': 'google-user-1', 'email': 'new-google-user@example.com', 'email_verified': True, 'given_name': 'New', 'family_name': 'User'}
			):
				response = self.client.post(
					reverse('accounts:google-login'),
					{'id_token': 'token-abc'},
					format='json',
				)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		user = User.objects.get(email='new-google-user@example.com')
		self.assertEqual(user.google_sub, 'google-user-1')
		self.assertEqual(user.role, User.Role.OWNER)
		self.assertEqual(user.account_status, User.AccountStatus.PENDING_VERIFICATION)
		self.assertFalse(user.email_verified)
		self.assertFalse(user.is_active)
		self.assertNotIn('access', response.data.get('data', {}))
		self.assertTrue(AuditEvent.objects.filter(event_type=AuditEvent.EventType.USER_REGISTERED, target_user=user).exists())

	def test_google_login_preserves_existing_account_role(self):
		user = self.active_user(email='lawyer-google@example.com', role=User.Role.LAWYER_VERIFIER)
		with self.settings(GOOGLE_OAUTH2_CLIENT_ID='client-123'):
			with self.patch_google_token(
				{'sub': 'google-lawyer-1', 'email': user.email, 'email_verified': True}
			):
				response = self.client.post(
					reverse('accounts:google-login'),
					{'id_token': 'token-lawyer'},
					format='json',
				)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['data']['user']['role'], User.Role.LAWYER_VERIFIER)

	def test_google_login_rejects_unverified_email(self):
		with self.settings(GOOGLE_OAUTH2_CLIENT_ID='client-123'):
			with self.patch_google_token(
				{'sub': 'google-unverified', 'email': 'unverified@example.com', 'email_verified': False}
			):
				response = self.client.post(
					reverse('accounts:google-login'),
					{'id_token': 'token-unverified'},
					format='json',
				)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertFalse(User.objects.filter(email='unverified@example.com').exists())
		self.assertNotIn('access', response.data.get('data', {}))

	def test_google_login_rejects_conflicting_subject_link(self):
		linked = self.active_user(email='google-owner-one@example.com', google_sub='google-shared-sub')
		other = self.active_user(email='google-owner-two@example.com')
		with self.settings(GOOGLE_OAUTH2_CLIENT_ID='client-123'):
			with self.patch_google_token(
				{'sub': 'google-shared-sub', 'email': other.email, 'email_verified': True}
			):
				response = self.client.post(
					reverse('accounts:google-login'),
					{'id_token': 'token-shared-sub'},
					format='json',
				)

		self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
		other.refresh_from_db()
		self.assertIsNone(other.google_sub)
		self.assertEqual(linked.google_sub, 'google-shared-sub')
		self.assertNotIn('access', response.data.get('data', {}))

	def test_google_login_rejects_inactive_existing_account(self):
		user = self.active_user(
			email='inactive-google@example.com',
			account_status=User.AccountStatus.SUSPENDED,
		)
		with self.settings(GOOGLE_OAUTH2_CLIENT_ID='client-123'):
			with self.patch_google_token(
				{'sub': 'google-inactive', 'email': user.email, 'email_verified': True}
			):
				response = self.client.post(
					reverse('accounts:google-login'),
					{'id_token': 'token-inactive'},
					format='json',
				)

		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
		user.refresh_from_db()
		self.assertFalse(user.google_sub)
		self.assertNotIn('access', response.data.get('data', {}))

	def test_google_link_binds_google_account_to_matching_local_user(self):
		user = self.active_user(email='linked@example.com')
		refresh = __import__('rest_framework_simplejwt.tokens', fromlist=['RefreshToken']).RefreshToken.for_user(user)
		self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

		with self.settings(GOOGLE_OAUTH2_CLIENT_ID='client-123'):
			with self.patch_google_token(
				{'sub': 'google-user-2', 'email': 'linked@example.com', 'email_verified': True, 'given_name': 'Linked', 'family_name': 'User'}
			):
				response = self.client.post(
					reverse('accounts:google-link'),
					{'id_token': 'token-xyz'},
					format='json',
				)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		user.refresh_from_db()
		self.assertEqual(user.google_sub, 'google-user-2')

	# --- 3. REFRESH TOKEN & ROTATION TESTS ---

	def test_token_refresh_rotates_refresh_token(self):
		self.active_user()
		login_response = self.client.post(
			reverse('accounts:login'),
			{'email': 'owner@example.com', 'password': 'Strong-password-123!'},
			format='json',
		)
		refresh_cookie = login_response.cookies['willchain_refresh'].value
		csrf_cookie = login_response.cookies['csrftoken'].value

		self.client.cookies['willchain_refresh'] = refresh_cookie
		self.client.cookies['csrftoken'] = csrf_cookie
		refresh_response = self.client.post(
			reverse('accounts:token-refresh'),
			HTTP_X_CSRFTOKEN=csrf_cookie,
		)
		self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
		self.assertIn('access', refresh_response.data['data'])
		self.assertIn('willchain_refresh', refresh_response.cookies)
		new_refresh_cookie = refresh_response.cookies['willchain_refresh'].value
		self.assertNotEqual(refresh_cookie, new_refresh_cookie)

	def test_token_refresh_rejects_missing_cookie(self):
		response = self.client.post(reverse('accounts:token-refresh'))
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	# --- 4. LOGOUT TESTS ---

	def test_logout_blacklists_refresh_token_and_clears_cookie(self):
		self.active_user()
		login_response = self.client.post(
			reverse('accounts:login'),
			{'email': 'owner@example.com', 'password': 'Strong-password-123!'},
			format='json',
		)
		access_token = login_response.data['data']['access']
		refresh_cookie = login_response.cookies['willchain_refresh'].value

		self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
		self.client.cookies['willchain_refresh'] = refresh_cookie
		logout_response = self.client.post(reverse('accounts:logout'))

		self.assertEqual(logout_response.status_code, status.HTTP_204_NO_CONTENT)
		self.assertEqual(logout_response.cookies['willchain_refresh'].value, '')
		self.assertTrue(AuditEvent.objects.filter(event_type=AuditEvent.EventType.LOGOUT).exists())

	# --- 5. PROFILE & ME ENDPOINT TESTS ---

	def test_profile_requires_authentication(self):
		response = self.client.get(reverse('accounts:me'))
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_active_user_can_read_own_profile(self):
		self.active_user()
		login_response = self.client.post(
			reverse('accounts:login'),
			{'email': 'owner@example.com', 'password': 'Strong-password-123!'},
			format='json',
		)
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['data']['access']}")

		response = self.client.get(reverse('accounts:me'))
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['data']['email'], 'owner@example.com')

	def test_profile_update_ignores_role_and_status_tampering(self):
		self.active_user()
		login_response = self.client.post(
			reverse('accounts:login'),
			{'email': 'owner@example.com', 'password': 'Strong-password-123!'},
			format='json',
		)
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['data']['access']}")

		response = self.client.patch(
			reverse('accounts:me'),
			{
				'first_name': 'Updated',
				'last_name': 'Name',
				'role': User.Role.ADMINISTRATOR,
				'account_status': User.AccountStatus.SUSPENDED,
			},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		user = User.objects.get(email='owner@example.com')
		self.assertEqual(user.first_name, 'Updated')
		self.assertEqual(user.role, User.Role.OWNER)
		self.assertEqual(user.account_status, User.AccountStatus.ACTIVE)

	def test_profile_avatar_upload_accepts_valid_image(self):
		self.active_user()
		login_response = self.client.post(
			reverse('accounts:login'),
			{'email': 'owner@example.com', 'password': 'Strong-password-123!'},
			format='json',
		)
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['data']['access']}")

		img_io = create_test_image('JPEG')
		avatar = SimpleUploadedFile('profile.jpg', img_io.read(), content_type='image/jpeg')
		response = self.client.patch(
			reverse('accounts:me'),
			{'avatar': avatar},
			format='multipart',
		)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIsNotNone(response.data['data']['avatar'])

	def test_profile_avatar_upload_rejects_non_image_extension(self):
		self.active_user()
		login_response = self.client.post(
			reverse('accounts:login'),
			{'email': 'owner@example.com', 'password': 'Strong-password-123!'},
			format='json',
		)
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['data']['access']}")

		bad_file = SimpleUploadedFile('exploit.svg', b'<svg><script>alert(1)</script></svg>', content_type='image/svg+xml')
		response = self.client.patch(
			reverse('accounts:me'),
			{'avatar': bad_file},
			format='multipart',
		)
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	# --- 6. PASSWORD CHANGE TESTS ---

	def test_change_password_with_valid_credentials(self):
		self.active_user()
		login_response = self.client.post(
			reverse('accounts:login'),
			{'email': 'owner@example.com', 'password': 'Strong-password-123!'},
			format='json',
		)
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['data']['access']}")

		response = self.client.post(
			reverse('accounts:change-password'),
			{
				'current_password': 'Strong-password-123!',
				'new_password': 'Brand-new-password-456!',
				'new_password_confirmation': 'Brand-new-password-456!',
			},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		user = User.objects.get(email='owner@example.com')
		self.assertTrue(user.check_password('Brand-new-password-456!'))
		self.assertTrue(AuditEvent.objects.filter(event_type=AuditEvent.EventType.PASSWORD_CHANGED).exists())

	def test_change_password_rejects_wrong_current_password(self):
		self.active_user()
		login_response = self.client.post(
			reverse('accounts:login'),
			{'email': 'owner@example.com', 'password': 'Strong-password-123!'},
			format='json',
		)
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['data']['access']}")

		response = self.client.post(
			reverse('accounts:change-password'),
			{
				'current_password': 'Incorrect-password-123!',
				'new_password': 'Brand-new-password-456!',
				'new_password_confirmation': 'Brand-new-password-456!',
			},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	# --- 7. FORGOT & RESET PASSWORD (CRITICAL VULNERABILITY CHECK) ---

	def test_forgot_password_sends_email(self):
		self.active_user()
		mail.outbox = []
		response = self.client.post(
			reverse('accounts:forgot-password'),
			{'email': 'owner@example.com'},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(mail.outbox), 1)
		self.assertIn('Reset your WillChain password', mail.outbox[0].subject)

	def test_reset_password_succeeds_with_valid_token(self):
		user = self.active_user()
		uid = urlsafe_base64_encode(force_bytes(user.pk))
		token = default_token_generator.make_token(user)

		response = self.client.post(
			reverse('accounts:reset-password'),
			{
				'uid': uid,
				'token': token,
				'new_password': 'New-reset-password-789!',
				'new_password_confirmation': 'New-reset-password-789!',
			},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		user.refresh_from_db()
		self.assertTrue(user.check_password('New-reset-password-789!'))

	def test_reset_password_MUST_REJECT_invalid_or_fake_token(self):
		"""CRITICAL VULNERABILITY REGRESSION TEST: Fake token must be rejected!"""
		user = self.active_user()
		uid = urlsafe_base64_encode(force_bytes(user.pk))

		response = self.client.post(
			reverse('accounts:reset-password'),
			{
				'uid': uid,
				'token': 'completely-fake-unauthorized-token',
				'new_password': 'Hacked-password-123!',
				'new_password_confirmation': 'Hacked-password-123!',
			},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		user.refresh_from_db()
		self.assertTrue(user.check_password('Strong-password-123!'))

	# --- 8. EMAIL VERIFICATION & REPLAY PROTECTION ---

	def test_email_verification_activates_account(self):
		user = self.active_user(email_verified=False, account_status=User.AccountStatus.PENDING_VERIFICATION)
		uid = urlsafe_base64_encode(force_bytes(user.pk))
		token = default_token_generator.make_token(user)

		response = self.client.post(
			reverse('accounts:verify-email'),
			{'uid': uid, 'token': token},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		user.refresh_from_db()
		self.assertTrue(user.email_verified)
		self.assertEqual(user.account_status, User.AccountStatus.ACTIVE)
		self.assertTrue(user.is_active)

	def test_email_verification_rejects_replay_on_already_verified_account(self):
		user = self.active_user(email_verified=True, account_status=User.AccountStatus.ACTIVE)
		uid = urlsafe_base64_encode(force_bytes(user.pk))
		token = default_token_generator.make_token(user)

		response = self.client.post(
			reverse('accounts:verify-email'),
			{'uid': uid, 'token': token},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(response.data['error']['code'], 'ALREADY_VERIFIED')

	def test_email_verification_cannot_reactivate_suspended_account(self):
		user = self.active_user(email_verified=False, account_status=User.AccountStatus.SUSPENDED)
		uid = urlsafe_base64_encode(force_bytes(user.pk))
		token = default_token_generator.make_token(user)

		response = self.client.post(
			reverse('accounts:verify-email'),
			{'uid': uid, 'token': token},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		user.refresh_from_db()
		self.assertEqual(user.account_status, User.AccountStatus.SUSPENDED)

	# --- 9. TESTATOR INVITATION WORKFLOW ---

	def test_testator_can_invite_witness(self):
		testator = self.active_user()
		will = Will.objects.create(owner=testator, title='Invitation Will', content={})
		login_response = self.client.post(
			reverse('accounts:login'),
			{'email': 'owner@example.com', 'password': 'Strong-password-123!'},
			format='json',
		)
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['data']['access']}")

		mail.outbox = []
		response = self.client.post(
			reverse('accounts:invitations'),
			{
				'email': 'witness@example.com',
				'first_name': 'Jane',
				'last_name': 'Witness',
				'role': Invitation.RoleChoices.WITNESS,
				'message': 'Please witness my digital will.',
				'will': will.pk,
			},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data['data']['email'], 'witness@example.com')
		self.assertEqual(response.data['data']['role'], 'WITNESS')
		self.assertEqual(response.data['data']['will'], will.pk)
		self.assertEqual(response.data['data']['will_title'], will.title)
		self.assertNotIn('token', response.data['data'])

		invitation = Invitation.objects.get(email='witness@example.com')
		self.assertEqual(invitation.inviter, testator)
		self.assertEqual(len(mail.outbox), 1)
		self.assertIn('Witness', mail.outbox[0].subject)
		sent_url = next(line for line in mail.outbox[0].body.splitlines() if '/accept-invitation?token=' in line)
		sent_token = parse_qs(urlsplit(sent_url).query)['token'][0]
		self.assertEqual(invitation.token_hash, Invitation.hash_token(sent_token))
		self.assertTrue(AuditEvent.objects.filter(event_type=AuditEvent.EventType.INVITATION_SENT).exists())

	def test_testator_can_invite_lawyer_but_uses_dedicated_beneficiary_flow(self):
		testator = self.active_user()
		will = Will.objects.create(owner=testator, title='Legal Review Will', content={})
		login_response = self.client.post(
			reverse('accounts:login'),
			{'email': 'owner@example.com', 'password': 'Strong-password-123!'},
			format='json',
		)
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['data']['access']}")

		# Invite Lawyer
		resp1 = self.client.post(
			reverse('accounts:invitations'),
			{'email': 'lawyer@example.com', 'role': Invitation.RoleChoices.LAWYER_VERIFIER, 'will': will.pk},
			format='json',
		)
		self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)

		# Invite Beneficiary
		resp2 = self.client.post(
			reverse('accounts:invitations'),
			{'email': 'beneficiary@example.com', 'role': Invitation.RoleChoices.BENEFICIARY},
			format='json',
		)
		self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertFalse(Invitation.objects.filter(email='beneficiary@example.com').exists())

	def test_collaborator_lists_only_accepted_will_scoped_invitations(self):
		owner = self.active_user(email='collaboration-owner@example.com')
		other_owner = self.active_user(email='other-collaboration-owner@example.com')
		collaborator = self.active_user(email='collaborator@example.com', role=User.Role.OWNER)
		will = Will.objects.create(owner=owner, title='Scoped Will', content={})
		other_will = Will.objects.create(owner=other_owner, title='Other Will', content={})
		Invitation.objects.create(
			inviter=owner,
			accepted_user=collaborator,
			will=will,
			email=collaborator.email,
			role=Invitation.RoleChoices.LAWYER_VERIFIER,
			status=Invitation.Status.ACCEPTED,
			accepted_at=timezone.now(),
		)
		Invitation.objects.create(
			inviter=other_owner,
			accepted_user=collaborator,
			will=other_will,
			email=collaborator.email,
			role=Invitation.RoleChoices.WITNESS,
			status=Invitation.Status.PENDING,
		)
		self.client.force_authenticate(collaborator)

		response = self.client.get(reverse('accounts:my-collaborations'))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(response.data['data']), 1)
		self.assertEqual(response.data['data'][0]['will'], will.pk)
		self.assertEqual(response.data['data'][0]['role'], Invitation.RoleChoices.LAWYER_VERIFIER)

	def test_invitee_must_verify_and_sign_in_before_accepting_invitation(self):
		testator = self.active_user()
		raw_token = Invitation.generate_token()
		invitation = Invitation.objects.create(
			inviter=testator,
			email='lawyer.sl@example.com',
			first_name='Alpha',
			last_name='Kargbo',
			role=Invitation.RoleChoices.LAWYER_VERIFIER,
			token_hash=Invitation.hash_token(raw_token),
		)

		# Query invitation details via GET
		get_resp = self.client.get(f"{reverse('accounts:accept-invitation')}?token={raw_token}")
		self.assertEqual(get_resp.status_code, status.HTTP_200_OK)
		self.assertEqual(get_resp.data['data']['role'], 'LAWYER_VERIFIER')
		self.assertEqual(get_resp.data['data']['email'], 'l***@example.com')
		self.assertNotIn('token', get_resp.data['data'])

		registration_response = self.client.post(
			reverse('accounts:accept-invitation'),
			{
				'token': raw_token,
				'email': 'lawyer.sl@example.com',
				'first_name': 'Alpha',
				'last_name': 'Kargbo',
				'phone_number': '+23276000111',
				'password': 'Lawyer-password-123!',
				'password_confirmation': 'Lawyer-password-123!',
			},
			format='json',
		)
		self.assertEqual(registration_response.status_code, status.HTTP_201_CREATED)
		self.assertNotIn('access', registration_response.data['data'])
		self.assertEqual(registration_response.data['data']['account_status'], User.AccountStatus.PENDING_VERIFICATION)

		# Verify created user
		new_user = User.objects.get(email='lawyer.sl@example.com')
		self.assertEqual(new_user.role, User.Role.LAWYER_VERIFIER)
		self.assertEqual(new_user.account_status, User.AccountStatus.PENDING_VERIFICATION)
		self.assertFalse(new_user.email_verified)
		self.assertIsNone(invitation.accepted_user)
		self.assertEqual(invitation.status, Invitation.Status.PENDING)

		uid = urlsafe_base64_encode(force_bytes(new_user.pk))
		verify_response = self.client.post(
			reverse('accounts:verify-email'),
			{'uid': uid, 'token': default_token_generator.make_token(new_user)},
			format='json',
		)
		self.assertEqual(verify_response.status_code, status.HTTP_200_OK)
		login_response = self.client.post(
			reverse('accounts:login'),
			{'email': new_user.email, 'password': 'Lawyer-password-123!'},
			format='json',
		)
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['data']['access']}")
		accept_response = self.client.post(
			reverse('accounts:accept-invitation'),
			{'token': raw_token},
			format='json',
		)
		self.assertEqual(accept_response.status_code, status.HTTP_200_OK)

		# Verify invitation status updated
		invitation.refresh_from_db()
		self.assertEqual(invitation.status, Invitation.Status.ACCEPTED)
		self.assertIsNotNone(invitation.accepted_at)
		self.assertEqual(invitation.accepted_user, new_user)
		self.assertIsNone(invitation.token_hash)
		self.assertTrue(AuditEvent.objects.filter(event_type=AuditEvent.EventType.INVITATION_ACCEPTED).exists())

	def test_existing_account_acceptance_does_not_change_global_role(self):
		owner = self.active_user(email='existing-invitee@example.com')
		raw_token = Invitation.generate_token()
		invitation = Invitation.objects.create(
			inviter=self.active_user(email='owner-inviter@example.com'),
			email=owner.email,
			role=Invitation.RoleChoices.LAWYER_VERIFIER,
			token_hash=Invitation.hash_token(raw_token),
		)
		from rest_framework_simplejwt.tokens import RefreshToken
		self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(owner).access_token}')

		response = self.client.post(
			reverse('accounts:accept-invitation'),
			{'token': raw_token},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		owner.refresh_from_db()
		invitation.refresh_from_db()
		self.assertEqual(owner.role, User.Role.OWNER)
		self.assertEqual(invitation.accepted_user, owner)

	def test_invitation_list_includes_minimal_profile_for_accepted_collaborator(self):
		owner = self.active_user(email='profile-owner@example.com')
		collaborator = self.active_user(
			email='profile-witness@example.com',
			first_name='Jane',
			last_name='Witness',
			avatar='avatars/jane.jpg',
			role=User.Role.WITNESS,
		)
		Invitation.objects.create(
			inviter=owner,
			accepted_user=collaborator,
			email=collaborator.email,
			first_name='Invited',
			role=Invitation.RoleChoices.WITNESS,
			status=Invitation.Status.ACCEPTED,
			accepted_at=timezone.now(),
		)
		from rest_framework_simplejwt.tokens import RefreshToken
		self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(owner).access_token}')

		response = self.client.get(reverse('accounts:invitations'))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['data'][0]['accepted_user_profile'], {
			'first_name': 'Jane',
			'last_name': 'Witness',
			'avatar': 'http://testserver/media/avatars/jane.jpg',
		})

	# --- 10. OBJECT PERMISSIONS AND IS_OWNER TESTS ---

	def test_is_owner_permission_allows_owner_and_rejects_others(self):
		owner = self.active_user(email='owner1@example.com')
		other_user = self.active_user(email='other@example.com')

		class MockResource:
			def __init__(self, owner):
				self.owner = owner

		resource = MockResource(owner=owner)
		permission = IsOwner()

		class MockRequest:
			def __init__(self, user):
				self.user = user

		self.assertTrue(permission.has_object_permission(MockRequest(owner), None, resource))
		self.assertFalse(permission.has_object_permission(MockRequest(other_user), None, resource))

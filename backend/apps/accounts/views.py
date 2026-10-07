from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.csrf import csrf_protect
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.models import AuditEvent
from .models import Invitation, User
from .permissions import IsActiveAccount, IsOwner, IsTestator
from .serializers import (
	ChangePasswordSerializer,
	ForgotPasswordSerializer,
	InvitationSerializer,
	LoginSerializer,
	RegistrationSerializer,
	ResetPasswordSerializer,
	UserSerializer,
	VerifyEmailSerializer,
)
from .services import (
	change_password,
	log_audit_event,
	send_email_verification,
	send_invitation_email,
	send_password_reset,
)

REFRESH_COOKIE_NAME = 'willchain_refresh'
REFRESH_COOKIE_MAX_AGE = 7 * 24 * 60 * 60


def set_refresh_cookie(response, refresh_token):
	response.set_cookie(
		REFRESH_COOKIE_NAME,
		str(refresh_token),
		max_age=REFRESH_COOKIE_MAX_AGE,
		httponly=True,
		secure=settings.AUTH_REFRESH_COOKIE_SECURE,
		samesite='Lax',
		path='/api/v1/auth/',
	)


class RegisterView(generics.CreateAPIView):
	serializer_class = RegistrationSerializer
	permission_classes = (permissions.AllowAny,)
	throttle_scope = 'auth'

	def create(self, request, *args, **kwargs):
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		user = serializer.save()
		send_email_verification(user)
		log_audit_event(
			AuditEvent.EventType.USER_REGISTERED,
			request=request,
			target_user=user,
			details={'email': user.email, 'role': user.role},
		)
		return Response(
			{
				'data': UserSerializer(user).data,
				'message': 'Account created. Complete email verification before logging in.',
			},
			status=status.HTTP_201_CREATED,
		)


class LoginView(APIView):
	permission_classes = (permissions.AllowAny,)
	throttle_scope = 'auth'

	def post(self, request):
		serializer = LoginSerializer(data=request.data)
		if not serializer.is_valid():
			log_audit_event(
				AuditEvent.EventType.LOGIN_FAILED,
				request=request,
				details={'attempted_email': request.data.get('email', '')},
			)
			serializer.is_valid(raise_exception=True)

		user = serializer.validated_data['user']
		refresh = RefreshToken.for_user(user)
		response = Response({'data': {'access': str(refresh.access_token), 'user': UserSerializer(user).data}})
		set_refresh_cookie(response, refresh)
		response.set_cookie('csrftoken', get_token(request), samesite='Lax')

		log_audit_event(
			AuditEvent.EventType.LOGIN_SUCCESS,
			request=request,
			actor=user,
			details={'email': user.email, 'role': user.role},
		)
		return response


@method_decorator(csrf_protect, name='dispatch')
class RefreshView(APIView):
	permission_classes = (permissions.AllowAny,)

	def post(self, request):
		raw_refresh = request.COOKIES.get(REFRESH_COOKIE_NAME)
		if not raw_refresh:
			return Response(
				{'error': {'code': 'AUTHENTICATION_REQUIRED', 'message': 'Refresh token is required.'}},
				status=status.HTTP_401_UNAUTHORIZED,
			)
		try:
			old_refresh = RefreshToken(raw_refresh)
			user = User.objects.get(pk=old_refresh['user_id'])
		except (TokenError, User.DoesNotExist, KeyError):
			return Response(
				{'error': {'code': 'INVALID_TOKEN', 'message': 'Refresh token is invalid.'}},
				status=status.HTTP_401_UNAUTHORIZED,
			)
		if user.account_status != User.AccountStatus.ACTIVE or not user.email_verified:
			return Response(
				{'error': {'code': 'ACCOUNT_INACTIVE', 'message': 'Account is not active.'}},
				status=status.HTTP_401_UNAUTHORIZED,
			)
		old_refresh.blacklist()
		new_refresh = RefreshToken.for_user(user)
		response = Response({'data': {'access': str(new_refresh.access_token)}})
		set_refresh_cookie(response, new_refresh)
		return response


class LogoutView(APIView):
	permission_classes = (IsActiveAccount,)

	def post(self, request):
		raw_refresh = request.COOKIES.get(REFRESH_COOKIE_NAME)
		if raw_refresh:
			try:
				RefreshToken(raw_refresh).blacklist()
			except TokenError:
				pass
		log_audit_event(
			AuditEvent.EventType.LOGOUT,
			request=request,
			actor=request.user,
		)
		response = Response(status=status.HTTP_204_NO_CONTENT)
		response.delete_cookie(REFRESH_COOKIE_NAME, path='/api/v1/auth/')
		return response


class MeView(generics.RetrieveUpdateAPIView):
	serializer_class = UserSerializer
	permission_classes = (IsActiveAccount, IsOwner)

	def get_object(self):
		obj = self.request.user
		self.check_object_permissions(self.request, obj)
		return obj

	def retrieve(self, request, *args, **kwargs):
		instance = self.get_object()
		serializer = self.get_serializer(instance)
		return Response({'data': serializer.data})

	def update(self, request, *args, **kwargs):
		partial = kwargs.pop('partial', False)
		instance = self.get_object()
		serializer = self.get_serializer(instance, data=request.data, partial=partial)
		serializer.is_valid(raise_exception=True)
		self.perform_update(serializer)
		return Response({'data': serializer.data, 'message': 'Profile updated successfully.'})


class ChangePasswordView(APIView):
	permission_classes = (IsActiveAccount,)

	def post(self, request):
		serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
		serializer.is_valid(raise_exception=True)
		change_password(request.user, serializer.validated_data['new_password'])
		log_audit_event(
			AuditEvent.EventType.PASSWORD_CHANGED,
			request=request,
			actor=request.user,
		)
		return Response({'data': None, 'message': 'Password changed successfully.'})


class ForgotPasswordView(APIView):
	permission_classes = (permissions.AllowAny,)
	throttle_scope = 'auth'

	def post(self, request):
		serializer = ForgotPasswordSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		user = User.objects.filter(
			email__iexact=serializer.validated_data['email'],
			account_status=User.AccountStatus.ACTIVE,
		).first()
		if user:
			send_password_reset(user)
			log_audit_event(
				AuditEvent.EventType.PASSWORD_RESET_REQUESTED,
				request=request,
				target_user=user,
				details={'email': user.email},
			)
		return Response({'data': None, 'message': 'If the account exists, reset instructions will be sent.'})


class ResetPasswordView(APIView):
	permission_classes = (permissions.AllowAny,)
	throttle_scope = 'auth'

	def post(self, request):
		serializer = ResetPasswordSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		user = serializer.validated_data['user']
		change_password(user, serializer.validated_data['new_password'])
		log_audit_event(
			AuditEvent.EventType.PASSWORD_RESET_COMPLETED,
			request=request,
			target_user=user,
			details={'email': user.email},
		)
		return Response({'data': None, 'message': 'Password reset successfully.'})


class VerifyEmailView(APIView):
	permission_classes = (permissions.AllowAny,)

	def post(self, request):
		serializer = VerifyEmailSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		try:
			user_id = force_str(urlsafe_base64_decode(serializer.validated_data['uid']))
			user = User.objects.get(pk=user_id)
		except (User.DoesNotExist, ValueError, TypeError):
			return Response(
				{'error': {'code': 'INVALID_VERIFICATION', 'message': 'Verification request is invalid.'}},
				status=status.HTTP_400_BAD_REQUEST,
			)

		if user.email_verified:
			return Response(
				{'error': {'code': 'ALREADY_VERIFIED', 'message': 'Email address is already verified. Please sign in.'}},
				status=status.HTTP_400_BAD_REQUEST,
			)

		if user.account_status != User.AccountStatus.PENDING_VERIFICATION:
			return Response(
				{'error': {'code': 'INVALID_STATUS', 'message': 'This account cannot be activated via email verification.'}},
				status=status.HTTP_400_BAD_REQUEST,
			)

		if not default_token_generator.check_token(user, serializer.validated_data['token']):
			return Response(
				{'error': {'code': 'INVALID_VERIFICATION', 'message': 'Verification link is invalid or has expired.'}},
				status=status.HTTP_400_BAD_REQUEST,
			)

		user.email_verified = True
		user.account_status = User.AccountStatus.ACTIVE
		user.save(update_fields=['email_verified', 'account_status', 'updated_at'])

		log_audit_event(
			AuditEvent.EventType.EMAIL_VERIFIED,
			request=request,
			target_user=user,
			details={'email': user.email},
		)
		return Response({'data': UserSerializer(user).data, 'message': 'Email verified successfully.'})


class InvitationListView(generics.ListCreateAPIView):
	serializer_class = InvitationSerializer
	permission_classes = (IsActiveAccount, IsTestator)

	def get_queryset(self):
		return Invitation.objects.filter(inviter=self.request.user)

	def list(self, request, *args, **kwargs):
		queryset = self.get_queryset()
		serializer = self.get_serializer(queryset, many=True)
		return Response({'data': serializer.data})

	@transaction.atomic
	def create(self, request, *args, **kwargs):
		serializer = self.get_serializer(data=request.data, context={'request': request})
		serializer.is_valid(raise_exception=True)
		invitation = serializer.save()
		AuditEvent.objects.create(
			event_type=AuditEvent.EventType.INVITATION_SENT,
			actor=request.user,
			details={'invitation_id': invitation.pk, 'role': invitation.role},
		)
		send_invitation_email(invitation, serializer.context['raw_invitation_token'])
		return Response(
			{
				'data': serializer.data,
				'message': f'Invitation sent to {invitation.email} as {invitation.get_role_display()}.',
			},
			status=status.HTTP_201_CREATED,
		)


class AcceptInvitationView(APIView):
	permission_classes = (permissions.AllowAny,)

	def get(self, request):
		token = request.query_params.get('token', '')
		if not isinstance(token, str) or not token:
			return Response({'error': {'message': 'Invitation token is required.'}}, status=status.HTTP_400_BAD_REQUEST)
		invitation = Invitation.objects.select_related('inviter').filter(
			token_hash=Invitation.hash_token(token),
		).first()
		if not invitation:
			return Response({'error': {'message': 'Invitation not found.'}}, status=status.HTTP_404_NOT_FOUND)

		if not invitation.is_valid():
			return Response({'error': {'message': 'Invitation has expired or has already been used.'}}, status=status.HTTP_400_BAD_REQUEST)

		local, _, domain = invitation.email.partition('@')
		return Response({'data': {
			'email': f'{local[:1]}***@{domain}' if domain else '***',
			'first_name': invitation.first_name,
			'last_name': invitation.last_name,
			'role': invitation.role,
			'role_display': invitation.get_role_display(),
			'inviter_name': f'{invitation.inviter.first_name} {invitation.inviter.last_name}'.strip() or 'WillChain member',
		}})

	@transaction.atomic
	def post(self, request):
		token = request.data.get('token')
		if not isinstance(token, str) or not token:
			return Response({'error': {'code': 'INVALID_INVITATION', 'message': 'Invitation is invalid or expired.'}}, status=status.HTTP_400_BAD_REQUEST)
		invitation = Invitation.objects.select_for_update().filter(token_hash=Invitation.hash_token(token)).first()
		if not invitation or not invitation.is_valid():
			return Response({'error': {'code': 'INVALID_INVITATION', 'message': 'Invitation is invalid or expired.'}}, status=status.HTTP_400_BAD_REQUEST)
		if invitation.role == Invitation.RoleChoices.BENEFICIARY:
			return Response({'error': {'code': 'DEDICATED_BENEFICIARY_FLOW', 'message': 'Use the beneficiary invitation workflow for this invitation.'}}, status=status.HTTP_400_BAD_REQUEST)

		if request.user and request.user.is_authenticated:
			if request.user.email.lower() != invitation.email.lower():
				raise PermissionDenied('This invitation belongs to a different account.')
			if request.user.account_status != User.AccountStatus.ACTIVE or not request.user.email_verified:
				raise PermissionDenied('Verify and activate your account before accepting this invitation.')
			user = request.user
			invitation.accepted_user = user
			invitation.status = Invitation.Status.ACCEPTED
			invitation.accepted_at = timezone.now()
			invitation.token_hash = None
			invitation.save(update_fields=['accepted_user', 'status', 'accepted_at', 'token_hash', 'updated_at'])
			AuditEvent.objects.create(
				event_type=AuditEvent.EventType.INVITATION_ACCEPTED,
				actor=user,
				target_user=user,
				details={'invitation_id': invitation.pk, 'invited_role': invitation.role},
			)
			return Response({'data': UserSerializer(user).data, 'message': 'Invitation accepted. This does not grant access to a will.'})

		email = request.data.get('email')
		if not isinstance(email, str) or email.strip().lower() != invitation.email.lower():
			return Response({'error': {'code': 'INVALID_INVITATION', 'message': 'Invitation or registration details are invalid.'}}, status=status.HTTP_400_BAD_REQUEST)
		if User.objects.filter(email__iexact=invitation.email).exists():
			return Response({'error': {'code': 'ACCOUNT_EXISTS', 'message': 'Sign in with the invited email to accept this invitation.'}}, status=status.HTTP_409_CONFLICT)
		registration_data = {
			'email': invitation.email,
			'first_name': request.data.get('first_name') or invitation.first_name or 'Invited',
			'last_name': request.data.get('last_name') or invitation.last_name or 'Member',
			'phone_number': request.data.get('phone_number', ''),
			'password': request.data.get('password'),
			'password_confirmation': request.data.get('password_confirmation'),
		}
		serializer = RegistrationSerializer(data=registration_data, context={'registration_role': invitation.role})
		serializer.is_valid(raise_exception=True)
		user = serializer.save()
		AuditEvent.objects.create(
			event_type=AuditEvent.EventType.USER_REGISTERED,
			target_user=user,
			details={'role': user.role, 'registration_source': 'collaborator_invitation'},
		)
		send_email_verification(user)
		return Response({
			'data': UserSerializer(user).data,
			'message': 'Account created. Verify your email, sign in, and reopen this link to accept the invitation.',
		}, status=status.HTTP_201_CREATED)

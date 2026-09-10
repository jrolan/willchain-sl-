from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.csrf import csrf_protect
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .permissions import IsActiveAccount
from .serializers import (
	ChangePasswordSerializer,
	ForgotPasswordSerializer,
	LoginSerializer,
	RegistrationSerializer,
	ResetPasswordSerializer,
	UserSerializer,
	VerifyEmailSerializer,
)
from .services import change_password, send_email_verification, send_password_reset

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

	def create(self, request, *args, **kwargs):
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		user = serializer.save()
		send_email_verification(user)
		return Response(
			{
				'data': UserSerializer(user).data,
				'message': 'Account created. Complete email verification before logging in.',
			},
			status=status.HTTP_201_CREATED,
		)


class LoginView(APIView):
	permission_classes = (permissions.AllowAny,)

	def post(self, request):
		serializer = LoginSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		user = serializer.validated_data['user']
		refresh = RefreshToken.for_user(user)
		response = Response({'data': {'access': str(refresh.access_token), 'user': UserSerializer(user).data}})
		set_refresh_cookie(response, refresh)
		response.set_cookie('csrftoken', get_token(request), samesite='Lax')
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
		response = Response(status=status.HTTP_204_NO_CONTENT)
		response.delete_cookie(REFRESH_COOKIE_NAME, path='/api/v1/auth/')
		return response


class MeView(generics.RetrieveUpdateAPIView):
	serializer_class = UserSerializer
	permission_classes = (IsActiveAccount,)

	def get_object(self):
		return self.request.user


class ChangePasswordView(APIView):
	permission_classes = (IsActiveAccount,)

	def post(self, request):
		serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
		serializer.is_valid(raise_exception=True)
		change_password(request.user, serializer.validated_data['new_password'])
		return Response({'data': None, 'message': 'Password changed successfully.'})


class ForgotPasswordView(APIView):
	permission_classes = (permissions.AllowAny,)

	def post(self, request):
		serializer = ForgotPasswordSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		user = User.objects.filter(
			email__iexact=serializer.validated_data['email'],
			account_status=User.AccountStatus.ACTIVE,
		).first()
		if user:
			send_password_reset(user)
		return Response({'data': None, 'message': 'If the account exists, reset instructions will be sent.'})


class ResetPasswordView(APIView):
	permission_classes = (permissions.AllowAny,)

	def post(self, request):
		serializer = ResetPasswordSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		change_password(serializer.validated_data['user'], serializer.validated_data['new_password'])
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
		if not default_token_generator.check_token(user, serializer.validated_data['token']):
			return Response(
				{'error': {'code': 'INVALID_VERIFICATION', 'message': 'Verification request is invalid.'}},
				status=status.HTTP_400_BAD_REQUEST,
			)
		user.email_verified = True
		user.account_status = User.AccountStatus.ACTIVE
		user.save(update_fields=['email_verified', 'account_status', 'updated_at'])
		return Response({'data': UserSerializer(user).data, 'message': 'Email verified successfully.'})

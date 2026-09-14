from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

from .models import Invitation, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'first_name',
            'last_name',
            'phone_number',
            'avatar',
            'role',
            'account_status',
            'email_verified',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'email',
            'role',
            'account_status',
            'email_verified',
            'created_at',
            'updated_at',
        )

    def validate_avatar(self, value):
        if value:
            max_size = 5 * 1024 * 1024  # 5MB
            if value.size > max_size:
                raise serializers.ValidationError('Avatar file size cannot exceed 5MB.')
            import os
            ext = os.path.splitext(value.name)[1].lower()
            if ext not in ('.jpg', '.jpeg', '.png', '.webp'):
                raise serializers.ValidationError('Only JPG, PNG, and WebP images are allowed.')
        return value


class RegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone_number = serializers.CharField(max_length=30, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirmation = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Unable to create an account with these details.')
        return value.lower()

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirmation']:
            raise serializers.ValidationError({'password_confirmation': 'Passwords do not match.'})
        validate_password(attrs['password'])
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirmation')
        password = validated_data.pop('password')
        return User.objects.create_user(password=password, **validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        user = authenticate(email=attrs['email'].lower(), password=attrs['password'])
        if not user or user.account_status != User.AccountStatus.ACTIVE or not user.email_verified:
            raise serializers.ValidationError('Invalid credentials or inactive account.')
        attrs['user'] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password_confirmation = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        user = self.context['request'].user
        if not user.check_password(attrs['current_password']):
            raise serializers.ValidationError({'current_password': 'Current password is incorrect.'})
        if attrs['new_password'] != attrs['new_password_confirmation']:
            raise serializers.ValidationError({'new_password_confirmation': 'Passwords do not match.'})
        validate_password(attrs['new_password'], user)
        return attrs


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password_confirmation = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirmation']:
            raise serializers.ValidationError({'new_password_confirmation': 'Passwords do not match.'})
        try:
            user_id = force_str(urlsafe_base64_decode(attrs['uid']))
            user = User.objects.get(pk=user_id)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError('Invalid password reset request.')

        if not default_token_generator.check_token(user, attrs['token']):
            raise serializers.ValidationError('Invalid or expired password reset token.')

        validate_password(attrs['new_password'], user)
        attrs['user'] = user
        return attrs


class VerifyEmailSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()


class InvitationSerializer(serializers.ModelSerializer):
    inviter_email = serializers.ReadOnlyField(source='inviter.email')

    class Meta:
        model = Invitation
        fields = (
            'id',
            'inviter_email',
            'email',
            'first_name',
            'last_name',
            'role',
            'status',
            'message',
            'expires_at',
            'created_at',
            'token',
        )
        read_only_fields = ('id', 'inviter_email', 'status', 'expires_at', 'created_at', 'token')

    def validate_role(self, value):
        if value not in (Invitation.RoleChoices.WITNESS, Invitation.RoleChoices.BENEFICIARY, Invitation.RoleChoices.LAWYER_VERIFIER):
            raise serializers.ValidationError('Role must be WITNESS, BENEFICIARY, or LAWYER_VERIFIER.')
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        email = attrs['email'].lower()
        if request and request.user.email.lower() == email:
            raise serializers.ValidationError({'email': 'You cannot invite yourself.'})
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError({'email': 'A user with this email is already registered.'})
        if Invitation.objects.filter(email__iexact=email, status=Invitation.Status.PENDING).exists():
            raise serializers.ValidationError({'email': 'A pending invitation already exists for this email.'})
        attrs['email'] = email
        return attrs

    def create(self, validated_data):
        validated_data['inviter'] = self.context['request'].user
        return super().create(validated_data)


class AcceptInvitationSerializer(serializers.Serializer):
    token = serializers.CharField()
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    phone_number = serializers.CharField(max_length=30, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirmation = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirmation']:
            raise serializers.ValidationError({'password_confirmation': 'Passwords do not match.'})
        try:
            invitation = Invitation.objects.get(token=attrs['token'])
        except Invitation.DoesNotExist:
            raise serializers.ValidationError({'token': 'Invalid invitation token.'})

        if not invitation.is_valid():
            raise serializers.ValidationError({'token': 'Invitation is expired or no longer pending.'})

        validate_password(attrs['password'])
        attrs['invitation'] = invitation
        return attrs

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken


def revoke_all_refresh_tokens(user):
    for outstanding_token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=outstanding_token)


def change_password(user, password):
    user.set_password(password)
    user.save(update_fields=['password', 'updated_at'])
    revoke_all_refresh_tokens(user)


def send_email_verification(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    verification_url = f'{settings.FRONTEND_BASE_URL}/verify-account?uid={uid}&token={token}'
    send_mail(
        'Verify your WillChain account',
        f'Complete account verification here: {verification_url}',
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def send_password_reset(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_url = f'{settings.FRONTEND_BASE_URL}/reset-password?uid={uid}&token={token}'
    send_mail(
        'Reset your WillChain password',
        f'Complete password reset here: {reset_url}',
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )

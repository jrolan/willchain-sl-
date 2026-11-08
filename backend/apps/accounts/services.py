import logging

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

try:
    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests as google_requests
except ImportError:  # pragma: no cover - optional dependency fallback
    google_id_token = None
    google_requests = None

from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.audit.models import AuditEvent

logger = logging.getLogger(__name__)


def log_audit_event(event_type, request=None, actor=None, target_user=None, details=None):
    ip_address = None
    user_agent = ''
    if request:
        if not actor and hasattr(request, 'user') and request.user.is_authenticated:
            actor = request.user
        ip_address = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
        if ip_address and ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:512]

    return AuditEvent.objects.create(
        event_type=event_type,
        actor=actor,
        target_user=target_user,
        ip_address=ip_address or None,
        user_agent=user_agent,
        details=details or {},
    )


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


def send_invitation_email(invitation, raw_token):
    accept_url = f'{settings.FRONTEND_BASE_URL}/accept-invitation?token={raw_token}'
    role_display = invitation.get_role_display()
    send_mail(
        f'You have been invited as a {role_display} on WillChain SL',
        f'Hello {invitation.first_name or ""},\n\n'
        f'{invitation.inviter.first_name} {invitation.inviter.last_name} ({invitation.inviter.email}) has invited you to join WillChain SL as a {role_display}.\n\n'
        f'Complete your registration and accept the invitation here:\n{accept_url}\n\n'
        f'This invitation link will expire in 7 days.',
        settings.DEFAULT_FROM_EMAIL,
        [invitation.email],
        fail_silently=False,
    )


def verify_google_id_token(id_token_value, client_id):
    if not id_token_value or not client_id:
        raise ValueError('Google OAuth client configuration is missing.')

    try:
        if google_id_token is None or google_requests is None:
            raise ValueError('Google token verification is unavailable.')
        return google_id_token.verify_oauth2_token(
            id_token_value,
            google_requests.Request(),
            client_id,
            clock_skew_in_seconds=10,
        )
    except ValueError as exc:
        logger.warning('Google ID token verification rejected (%s).', type(exc).__name__)
        raise ValueError('Google ID token is invalid.') from exc
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning('Google ID token verification errored (%s).', type(exc).__name__)
        raise ValueError('Google ID token is invalid.') from exc
import secrets

from django.conf import settings
from django.core.mail import send_mail

from apps.audit.models import AuditEvent


def generate_identity_verification_code():
    return str(secrets.randbelow(900000) + 100000).zfill(6)


def send_identity_verification_code(recipient_email, code):
    send_mail(
        'WillChain beneficiary identity check',
        f'Your beneficiary verification code is {code}. This code expires in 10 minutes.',
        settings.DEFAULT_FROM_EMAIL,
        [recipient_email],
        fail_silently=False,
    )


def record_beneficiary_audit(event_type, request=None, actor=None, target_user=None, details=None):
    ip_address = None
    user_agent = ''
    if request:
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
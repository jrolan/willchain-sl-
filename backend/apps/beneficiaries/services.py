from django.conf import settings
from django.core.mail import send_mail
from apps.audit.models import AuditEvent
from urllib.parse import urlencode


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


def send_beneficiary_invitation_email(invitation, raw_token):
    invitation_url = (
        f"{settings.FRONTEND_BASE_URL.rstrip('/')}/beneficiary-invitation?"
        f"{urlencode({'token': raw_token})}"
    )
    send_mail(
        'You have been invited to WillChain SL',
        f'You have been invited to join a will as a beneficiary.\n\n'
        f'Invitation link: {invitation_url}\n\n'
        f'This link expires in 7 days.',
        settings.DEFAULT_FROM_EMAIL,
        [invitation.recipient_email],
        fail_silently=False,
    )
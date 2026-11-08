from apps.audit.models import AuditEvent


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
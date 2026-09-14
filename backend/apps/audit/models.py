from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    class EventType(models.TextChoices):
        USER_REGISTERED = 'USER_REGISTERED', 'User registered'
        LOGIN_SUCCESS = 'LOGIN_SUCCESS', 'Login successful'
        LOGIN_FAILED = 'LOGIN_FAILED', 'Login failed'
        LOGOUT = 'LOGOUT', 'User logged out'
        PASSWORD_CHANGED = 'PASSWORD_CHANGED', 'Password changed'
        PASSWORD_RESET_REQUESTED = 'PASSWORD_RESET_REQUESTED', 'Password reset requested'
        PASSWORD_RESET_COMPLETED = 'PASSWORD_RESET_COMPLETED', 'Password reset completed'
        EMAIL_VERIFIED = 'EMAIL_VERIFIED', 'Email verified'
        INVITATION_SENT = 'INVITATION_SENT', 'Invitation sent'
        INVITATION_ACCEPTED = 'INVITATION_ACCEPTED', 'Invitation accepted'
        ACCOUNT_STATUS_CHANGED = 'ACCOUNT_STATUS_CHANGED', 'Account status changed'
        SECURITY_ALERT = 'SECURITY_ALERT', 'Security alert'

    event_type = models.CharField(max_length=64, choices=EventType.choices, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_events_created',
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_events_targeted',
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['event_type', 'created_at']),
        ]

    def __str__(self):
        actor_email = self.actor.email if self.actor else 'System/Anonymous'
        return f'[{self.created_at:%Y-%m-%d %H:%M:%S}] {self.event_type} by {actor_email}'

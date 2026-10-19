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
        WILL_CREATED = 'WILL_CREATED', 'Will created'
        WILL_ACCESSED = 'WILL_ACCESSED', 'Will accessed'
        WILL_UPDATED = 'WILL_UPDATED', 'Will updated'
        WILL_FINALIZED = 'WILL_FINALIZED', 'Will finalized'
        WILL_DELETED = 'WILL_DELETED', 'Will deleted'
        WILL_ACCESS_DENIED = 'WILL_ACCESS_DENIED', 'Will access denied'
        SECURITY_ALERT = 'SECURITY_ALERT', 'Security alert'
        VERIFICATION_CASE_CREATED = 'VERIFICATION_CASE_CREATED', 'Verification case created'
        VERIFICATION_CASE_SUBMITTED = 'VERIFICATION_CASE_SUBMITTED', 'Verification case submitted'
        VERIFICATION_CASE_ASSIGNED = 'VERIFICATION_CASE_ASSIGNED', 'Verification case assigned'
        VERIFICATION_DECISION_RECORDED = 'VERIFICATION_DECISION_RECORDED', 'Verification decision recorded'
        WILL_DISCLOSURE_AUTHORIZED = 'WILL_DISCLOSURE_AUTHORIZED', 'Will copy disclosure authorised'
        WILL_DISCLOSURE_REVOKED = 'WILL_DISCLOSURE_REVOKED', 'Will copy disclosure revoked'
        VERIFICATION_EVIDENCE_UPLOADED = 'VERIFICATION_EVIDENCE_UPLOADED', 'Verification evidence uploaded'
        VERIFICATION_ELIGIBILITY_CHECKED = 'VERIFICATION_ELIGIBILITY_CHECKED', 'Claimant eligibility checked'
        VERIFICATION_CASE_RESUBMITTED = 'VERIFICATION_CASE_RESUBMITTED', 'Verification case resubmitted'
        VERIFICATION_CASE_WITHDRAWN = 'VERIFICATION_CASE_WITHDRAWN', 'Verification case withdrawn'
        VERIFICATION_REVIEW_BEGUN = 'VERIFICATION_REVIEW_BEGUN', 'Verification review begun'
        VERIFICATION_INFORMATION_REQUESTED = 'VERIFICATION_INFORMATION_REQUESTED', 'Verification information requested'
        VERIFICATION_EVIDENCE_SUFFICIENCY_CHANGED = 'VERIFICATION_EVIDENCE_SUFFICIENCY_CHANGED', 'Verification evidence sufficiency changed'

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

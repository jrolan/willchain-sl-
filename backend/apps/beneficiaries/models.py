import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.wills.models import Will


class WillBeneficiary(models.Model):
    class RelationshipType(models.TextChoices):
        PRIMARY = 'PRIMARY', 'Primary'
        CONTINGENT = 'CONTINGENT', 'Contingent'
        RESIDUAL = 'RESIDUAL', 'Residual'
        WITNESS = 'WITNESS', 'Witness'
        LAWYER = 'LAWYER', 'Lawyer'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        ACTIVE = 'ACTIVE', 'Active'
        DECLINED = 'DECLINED', 'Declined'
        REVOKED = 'REVOKED', 'Revoked'

    will = models.ForeignKey(
        Will,
        on_delete=models.CASCADE,
        related_name='beneficiaries',
    )
    beneficiary_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='beneficiary_relationships',
        null=True,
        blank=True,
    )
    normalized_email = models.EmailField(db_index=True)
    full_name = models.CharField(max_length=200, blank=True)
    relationship_type = models.CharField(
        max_length=32,
        choices=RelationshipType.choices,
        default=RelationshipType.PRIMARY,
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=['will', 'normalized_email'],
                condition=Q(status__in=['PENDING', 'ACTIVE']),
                name='unique_active_or_pending_beneficiary_email_per_will',
            ),
            models.UniqueConstraint(
                fields=['will', 'beneficiary_user'],
                condition=Q(beneficiary_user__isnull=False, status__in=['PENDING', 'ACTIVE']),
                name='unique_active_or_pending_beneficiary_user_per_will',
            ),
        ]
        indexes = [
            models.Index(fields=['will', 'status'], name='ben_will_status_idx'),
            models.Index(fields=['beneficiary_user', 'status'], name='ben_user_status_idx'),
            models.Index(fields=['normalized_email', 'status'], name='ben_email_status_idx'),
        ]

    def revoke(self):
        if self.status == self.Status.REVOKED:
            return self
        self.status = self.Status.REVOKED
        self.revoked_at = timezone.now()
        self.save(update_fields=['status', 'revoked_at', 'updated_at'])

        now = timezone.now()
        pending_invitations = self.invitations.filter(status__in=[BeneficiaryInvitation.Status.PENDING, BeneficiaryInvitation.Status.EXPIRED])
        for invitation in pending_invitations:
            if invitation.status == BeneficiaryInvitation.Status.PENDING:
                invitation.status = (
                    BeneficiaryInvitation.Status.EXPIRED
                    if invitation.expires_at <= now
                    else BeneficiaryInvitation.Status.REVOKED
                )
                if invitation.status == BeneficiaryInvitation.Status.REVOKED:
                    invitation.responded_at = now
            invitation.token_hash = None
            invitation.save(update_fields=['status', 'token_hash', 'responded_at', 'updated_at'])
        return self

    def __str__(self):
        return f'{self.full_name or self.normalized_email} ({self.will_id})'


class BeneficiaryInvitation(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        ACCEPTED = 'ACCEPTED', 'Accepted'
        DECLINED = 'DECLINED', 'Declined'
        REVOKED = 'REVOKED', 'Revoked'
        EXPIRED = 'EXPIRED', 'Expired'

    relationship = models.ForeignKey(
        WillBeneficiary,
        on_delete=models.CASCADE,
        related_name='invitations',
    )
    inviter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_beneficiary_invitations',
        null=True,
        blank=True,
    )
    recipient_email = models.EmailField(db_index=True)
    token_hash = models.CharField(max_length=128, unique=True, null=True, blank=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    expires_at = models.DateTimeField()
    sent_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=['relationship'],
                condition=Q(status='PENDING'),
                name='unique_pending_invitation_per_relationship',
            ),
        ]
        indexes = [
            models.Index(fields=['recipient_email', 'status'], name='ben_rec_status_idx'),
            models.Index(fields=['relationship', 'status'], name='ben_rel_status_idx'),
        ]

    @staticmethod
    def generate_token():
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_token(raw_token):
        return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

    def set_token(self, raw_token):
        self.token_hash = self.hash_token(raw_token)
        if self.pk:
            self.save(update_fields=['token_hash', 'updated_at'])

    def token_matches(self, raw_token):
        return bool(self.token_hash and hmac.compare_digest(self.token_hash, self.hash_token(raw_token)))

    def is_valid(self):
        return self.status == self.Status.PENDING and self.expires_at > timezone.now()

    def __str__(self):
        return f'{self.recipient_email} invitation for will {self.relationship.will_id}'

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

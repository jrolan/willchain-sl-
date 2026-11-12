import hashlib
import json

from django.conf import settings
from django.db import models
from django.utils import timezone


class Will(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        FINALIZED = 'FINALIZED', 'Finalized'
        ARCHIVED = 'ARCHIVED', 'Archived'

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='wills',
    )
    title = models.CharField(max_length=200)
    content = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    version = models.PositiveIntegerField(default=1)
    finalized_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-updated_at',)
        indexes = [
            models.Index(fields=['owner', 'status']),
        ]

    def __str__(self):
        return f'{self.title} ({self.owner.email})'

    @property
    def is_read_only(self):
        return self.status in {self.Status.FINALIZED, self.Status.ARCHIVED}

    @property
    def is_editable(self):
        return self.status == self.Status.DRAFT

    def finalize(self):
        if self.status != self.Status.DRAFT:
            raise ValueError('Only draft wills can be finalized.')
        self.status = self.Status.FINALIZED
        self.finalized_at = timezone.now()
        self.version += 1
        self.save(update_fields=['status', 'finalized_at', 'version', 'updated_at'])


class WitnessAttestation(models.Model):
    class Status(models.TextChoices):
        ATTESTED = 'ATTESTED', 'Attested'
        DECLINED = 'DECLINED', 'Declined'

    invitation = models.OneToOneField(
        'accounts.Invitation',
        on_delete=models.PROTECT,
        related_name='witness_attestation',
    )
    will = models.ForeignKey(
        Will,
        on_delete=models.PROTECT,
        related_name='witness_attestations',
    )
    witness = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='witness_attestations',
    )
    status = models.CharField(max_length=16, choices=Status.choices)
    will_version = models.PositiveIntegerField()
    will_content_hash = models.CharField(max_length=64)
    responded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ('-responded_at',)

    @staticmethod
    def hash_will_content(content):
        canonical_content = json.dumps(content, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        return hashlib.sha256(canonical_content.encode('utf-8')).hexdigest()

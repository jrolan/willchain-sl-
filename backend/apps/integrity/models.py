from django.conf import settings
from django.db import models
from django.db.models import Q


class AnchorStatus(models.TextChoices):
    QUEUED = 'QUEUED', 'Queued'
    SUBMITTING = 'SUBMITTING', 'Submitting'
    SUBMITTED = 'SUBMITTED', 'Submitted'
    CONFIRMED = 'CONFIRMED', 'Confirmed'
    FAILED = 'FAILED', 'Failed'


class WillIntegrityRecord(models.Model):
    will = models.OneToOneField(
        'wills.Will',
        on_delete=models.PROTECT,
        related_name='integrity_record',
    )
    record_reference = models.CharField(max_length=64, unique=True)
    finalized_version = models.PositiveIntegerField()
    content_digest = models.CharField(max_length=64)
    commitment = models.CharField(max_length=64)
    encrypted_salt = models.TextField()
    encrypted_snapshot = models.TextField()
    network = models.CharField(max_length=64)
    chain_id = models.PositiveBigIntegerField()
    contract_address = models.CharField(max_length=42, blank=True)
    anchor_status = models.CharField(
        max_length=16,
        choices=AnchorStatus.choices,
        default=AnchorStatus.QUEUED,
        db_index=True,
    )
    transaction_hash = models.CharField(max_length=66, blank=True)
    block_number = models.PositiveBigIntegerField(null=True, blank=True)
    confirmations = models.PositiveIntegerField(default=0)
    encrypted_raw_transaction = models.TextField(blank=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error_code = models.CharField(max_length=48, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.CheckConstraint(condition=Q(finalized_version__gt=0), name='integrity_will_version_positive'),
        ]
        indexes = [
            models.Index(fields=('anchor_status', 'updated_at'), name='integrity_will_status_idx'),
        ]


class DocumentIntegrityRecord(models.Model):
    will_record = models.ForeignKey(
        WillIntegrityRecord,
        on_delete=models.PROTECT,
        related_name='document_records',
    )
    document = models.ForeignKey(
        'documents.WillDocument',
        on_delete=models.PROTECT,
        related_name='blockchain_integrity_records',
    )
    document_version = models.PositiveIntegerField()
    record_reference = models.CharField(max_length=64, unique=True)
    content_digest = models.CharField(max_length=64)
    commitment = models.CharField(max_length=64, blank=True)
    encrypted_salt = models.TextField()
    network = models.CharField(max_length=64)
    chain_id = models.PositiveBigIntegerField()
    contract_address = models.CharField(max_length=42, blank=True)
    anchor_status = models.CharField(
        max_length=16,
        choices=AnchorStatus.choices,
        default=AnchorStatus.QUEUED,
        db_index=True,
    )
    transaction_hash = models.CharField(max_length=66, blank=True)
    block_number = models.PositiveBigIntegerField(null=True, blank=True)
    confirmations = models.PositiveIntegerField(default=0)
    encrypted_raw_transaction = models.TextField(blank=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error_code = models.CharField(max_length=48, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(fields=('document', 'document_version'), name='integrity_doc_version_unique'),
            models.CheckConstraint(condition=Q(document_version__gt=0), name='integrity_doc_version_positive'),
        ]
        indexes = [
            models.Index(fields=('anchor_status', 'updated_at'), name='integrity_doc_status_idx'),
        ]


class WillIntegrityVerification(models.Model):
    class Result(models.TextChoices):
        MATCH = 'MATCH', 'Match'
        MISMATCH = 'MISMATCH', 'Mismatch'
        PENDING = 'PENDING', 'Pending'
        UNAVAILABLE = 'UNAVAILABLE', 'Unavailable'

    will_record = models.ForeignKey(
        WillIntegrityRecord,
        on_delete=models.PROTECT,
        related_name='verifications',
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='will_integrity_verifications',
    )
    result = models.CharField(max_length=16, choices=Result.choices, db_index=True)
    content_matches = models.BooleanField(null=True, blank=True)
    chain_matches = models.BooleanField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)
    checked_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ('-checked_at',)
        indexes = [
            models.Index(fields=('will_record', 'checked_at'), name='integrity_check_created_idx'),
        ]

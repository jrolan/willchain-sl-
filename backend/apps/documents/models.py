import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.wills.models import Will


class WillDocument(models.Model):
    class DocumentType(models.TextChoices):
        IDENTITY = 'IDENTITY', 'Identity document'
        PASSPORT = 'PASSPORT', 'Passport'
        LAND_PROPERTY = 'LAND_PROPERTY', 'Land or property record'
        MARRIAGE_CERTIFICATE = 'MARRIAGE_CERTIFICATE', 'Marriage certificate'
        BIRTH_CERTIFICATE = 'BIRTH_CERTIFICATE', 'Birth certificate'
        OTHER = 'OTHER', 'Other supporting evidence'

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        REPLACED = 'REPLACED', 'Replaced'
        DELETED = 'DELETED', 'Soft deleted'

    will = models.ForeignKey(Will, on_delete=models.CASCADE, related_name='documents')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_will_documents',
    )
    document_type = models.CharField(max_length=32, choices=DocumentType.choices)
    description = models.CharField(max_length=255, blank=True)
    original_filename = models.CharField(max_length=255)
    storage_key = models.CharField(max_length=80, unique=True)
    media_type = models.CharField(max_length=64)
    file_size = models.PositiveBigIntegerField()
    checksum_sha256 = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    version_group = models.UUIDField(default=uuid.uuid4, db_index=True)
    version = models.PositiveIntegerField(default=1)
    replaced_from = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True, related_name='replacement_versions'
    )
    replaced_by = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True, related_name='previous_versions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deleted_will_documents',
    )

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.CheckConstraint(condition=Q(file_size__gt=0), name='document_file_size_positive'),
            models.CheckConstraint(condition=Q(version__gt=0), name='document_version_positive'),
            models.UniqueConstraint(fields=('will', 'version_group', 'version'), name='unique_will_document_version'),
        ]
        indexes = [
            models.Index(fields=('will', 'status'), name='doc_will_status_idx'),
            models.Index(fields=('version_group', 'version'), name='doc_version_group_idx'),
        ]


class DocumentIntegrityCheck(models.Model):
    class Result(models.TextChoices):
        VALID = 'VALID', 'Valid'
        MISMATCH = 'MISMATCH', 'Mismatch'
        ERROR = 'ERROR', 'Error'

    document = models.ForeignKey(WillDocument, on_delete=models.CASCADE, related_name='integrity_checks')
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='document_integrity_checks',
    )
    result = models.CharField(max_length=16, choices=Result.choices, db_index=True)
    expected_checksum = models.CharField(max_length=64)
    computed_checksum = models.CharField(max_length=64, blank=True)
    error_code = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [models.Index(fields=('document', 'created_at'), name='doc_check_created_idx')]
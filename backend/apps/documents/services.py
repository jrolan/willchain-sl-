from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditEvent
from .models import DocumentIntegrityCheck, WillDocument
from .storage import PrivateStorageError, private_document_storage
from .validation import MAX_DOCUMENT_SIZE_BYTES


def record_document_audit(*, request, actor, will_id, document_id, action, outcome='SUCCESS'):
    ip_address = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    if ip_address and ',' in ip_address:
        ip_address = ip_address.split(',')[0].strip()
    return AuditEvent.objects.create(
        event_type=AuditEvent.EventType.SECURITY_ALERT,
        actor=actor,
        ip_address=ip_address or None,
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:512],
        details={
            'resource': 'will_document',
            'action': action,
            'outcome': outcome,
            'will_id': will_id,
            'document_id': document_id,
        },
    )


def create_document(*, will, actor, request, validated, document_type, description=''):
    storage_key = private_document_storage.save(validated)
    try:
        with transaction.atomic():
            document = WillDocument.objects.create(
                will=will,
                uploaded_by=actor,
                document_type=document_type,
                description=description,
                original_filename=validated.filename,
                storage_key=storage_key,
                media_type=validated.media_type,
                file_size=validated.file_size,
                checksum_sha256=validated.checksum_sha256,
            )
            record_document_audit(
                request=request,
                actor=actor,
                will_id=will.pk,
                document_id=document.pk,
                action='UPLOAD',
            )
        return document
    except Exception:
        private_document_storage.delete(storage_key)
        raise


def replace_document(*, previous, actor, request, validated):
    storage_key = private_document_storage.save(validated)
    try:
        with transaction.atomic():
            previous.status = WillDocument.Status.REPLACED
            previous.save(update_fields=('status', 'updated_at'))
            replacement = WillDocument.objects.create(
                will=previous.will,
                uploaded_by=actor,
                document_type=previous.document_type,
                description=previous.description,
                original_filename=validated.filename,
                storage_key=storage_key,
                media_type=validated.media_type,
                file_size=validated.file_size,
                checksum_sha256=validated.checksum_sha256,
                version_group=previous.version_group,
                version=previous.version + 1,
                replaced_from=previous,
            )
            previous.replaced_by = replacement
            previous.save(update_fields=('replaced_by', 'updated_at'))
            record_document_audit(
                request=request,
                actor=actor,
                will_id=previous.will_id,
                document_id=replacement.pk,
                action='REPLACE',
            )
        return replacement
    except Exception:
        private_document_storage.delete(storage_key)
        raise


def verify_document_integrity(*, document, actor, request):
    try:
        computed = private_document_storage.checksum(document.storage_key)
        result = (
            DocumentIntegrityCheck.Result.VALID
            if computed == document.checksum_sha256
            else DocumentIntegrityCheck.Result.MISMATCH
        )
        error_code = ''
    except PrivateStorageError:
        computed = ''
        result = DocumentIntegrityCheck.Result.ERROR
        error_code = 'STORAGE_UNAVAILABLE'

    with transaction.atomic():
        check = DocumentIntegrityCheck.objects.create(
            document=document,
            actor=actor,
            result=result,
            expected_checksum=document.checksum_sha256,
            computed_checksum=computed,
            error_code=error_code,
        )
        record_document_audit(
            request=request,
            actor=actor,
            will_id=document.will_id,
            document_id=document.pk,
            action='INTEGRITY_CHECK',
            outcome=result,
        )
    return check


def soft_delete_document(*, document, actor, request):
    document.status = WillDocument.Status.DELETED
    document.deleted_at = timezone.now()
    document.deleted_by = actor
    document.save(update_fields=('status', 'deleted_at', 'deleted_by', 'updated_at'))
    record_document_audit(
        request=request,
        actor=actor,
        will_id=document.will_id,
        document_id=document.pk,
        action='SOFT_DELETE',
    )


def update_document_metadata(*, document, actor, request, values):
    for field, value in values.items():
        setattr(document, field, value)
    document.save(update_fields=(*values.keys(), 'updated_at'))
    record_document_audit(
        request=request,
        actor=actor,
        will_id=document.will_id,
        document_id=document.pk,
        action='METADATA_UPDATE',
    )


DOCUMENT_UPLOAD_LIMIT = MAX_DOCUMENT_SIZE_BYTES
from django.conf import settings

from apps.documents.models import WillDocument
from apps.documents.storage import PrivateStorageError, private_document_storage
from .blockchain import BlockchainConfigurationError, BlockchainUnavailable, verify_anchor
from .crypto import (
    IntegrityCryptoError,
    canonical_json,
    commitment_for,
    decrypt_secret,
    encrypt_secret,
    new_record_reference,
    new_salt,
    sha256_hex,
)
from .models import AnchorStatus, DocumentIntegrityRecord, WillIntegrityRecord, WillIntegrityVerification


def will_snapshot_payload(will):
    return {
        'schema': 'willchain-will-integrity-v1',
        'title': will.title,
        'content': will.content,
        'version': will.version,
        'finalized_at': will.finalized_at.isoformat() if will.finalized_at else None,
    }


def create_will_integrity_record(will):
    from apps.wills.models import Will

    if will.status != Will.Status.FINALIZED or not will.finalized_at:
        raise ValueError('Only a finalized will can receive an integrity snapshot.')
    existing = WillIntegrityRecord.objects.filter(will=will).first()
    if existing:
        return existing

    snapshot_bytes = canonical_json(will_snapshot_payload(will))
    digest = sha256_hex(snapshot_bytes)
    reference = new_record_reference()
    salt = new_salt()
    record = WillIntegrityRecord.objects.create(
        will=will,
        record_reference=reference,
        finalized_version=will.version,
        content_digest=digest,
        commitment=commitment_for(reference, digest, salt),
        encrypted_salt=encrypt_secret('will-salt', salt),
        encrypted_snapshot=encrypt_secret('will-snapshot', snapshot_bytes),
        network=settings.INTEGRITY_NETWORK_NAME,
        chain_id=settings.INTEGRITY_CHAIN_ID,
        contract_address=settings.INTEGRITY_CONTRACT_ADDRESS,
    )
    _create_document_integrity_records(will, record)
    return record


def _create_document_integrity_records(will, will_record):
    documents = WillDocument.objects.filter(
        will=will,
        status=WillDocument.Status.ACTIVE,
    ).order_by('pk')
    for document in documents:
        reference = new_record_reference()
        salt = new_salt()
        error_code = ''
        try:
            digest = private_document_storage.checksum(document.storage_key)
            if digest != document.checksum_sha256:
                error_code = 'DOCUMENT_CONTENT_MISMATCH'
        except PrivateStorageError:
            digest = document.checksum_sha256
            error_code = 'DOCUMENT_STORAGE_UNAVAILABLE'

        record = DocumentIntegrityRecord(
            will_record=will_record,
            document=document,
            document_version=document.version,
            record_reference=reference,
            content_digest=digest,
            commitment=(
                commitment_for(reference, digest, salt)
                if not error_code
                else ''
            ),
            encrypted_salt=encrypt_secret('document-salt', salt),
            network=settings.INTEGRITY_NETWORK_NAME,
            chain_id=settings.INTEGRITY_CHAIN_ID,
            contract_address=settings.INTEGRITY_CONTRACT_ADDRESS,
        )
        if error_code:
            record.anchor_status = AnchorStatus.FAILED
            record.last_error_code = error_code
        record.save()


def _verify_documents(will_record):
    results = []
    for record in will_record.document_records.select_related('document').all():
        if not record.commitment and record.last_error_code == 'DOCUMENT_CONTENT_MISMATCH':
            results.append({'document_id': record.document_id, 'result': 'MISMATCH'})
            continue
        if not record.commitment and record.last_error_code == 'DOCUMENT_STORAGE_UNAVAILABLE':
            results.append({'document_id': record.document_id, 'result': 'UNAVAILABLE'})
            continue
        if not record.commitment or record.anchor_status != AnchorStatus.CONFIRMED:
            results.append({'document_id': record.document_id, 'result': 'PENDING'})
            continue
        try:
            current_digest = private_document_storage.checksum(record.document.storage_key)
        except PrivateStorageError:
            results.append({'document_id': record.document_id, 'result': 'UNAVAILABLE'})
            continue
        if current_digest != record.content_digest:
            results.append({'document_id': record.document_id, 'result': 'MISMATCH'})
            continue
        try:
            salt = decrypt_secret('document-salt', record.encrypted_salt)
            reconstructed = commitment_for(record.record_reference, current_digest, salt)
            chain_matches = reconstructed == record.commitment and verify_anchor(record)
            if not chain_matches and record.anchor_status == AnchorStatus.CONFIRMED:
                record.anchor_status = AnchorStatus.FAILED
                record.last_error_code = 'CHAIN_COMMITMENT_MISMATCH'
                record.save(update_fields=['anchor_status', 'last_error_code', 'updated_at'])
        except (IntegrityCryptoError, BlockchainConfigurationError, BlockchainUnavailable):
            results.append({'document_id': record.document_id, 'result': 'UNAVAILABLE'})
            continue
        results.append({
            'document_id': record.document_id,
            'result': 'MATCH' if chain_matches else 'MISMATCH',
        })
    return results


def verify_will_integrity(will_record, actor):
    try:
        snapshot_bytes = decrypt_secret('will-snapshot', will_record.encrypted_snapshot)
        original_digest = sha256_hex(snapshot_bytes)
        current_digest = sha256_hex(canonical_json(will_snapshot_payload(will_record.will)))
        salt = decrypt_secret('will-salt', will_record.encrypted_salt)
        reconstructed_commitment = commitment_for(
            will_record.record_reference,
            original_digest,
            salt,
        )
        content_matches = (
            original_digest == will_record.content_digest
            and current_digest == will_record.content_digest
        )
        commitment_matches = reconstructed_commitment == will_record.commitment
    except (IntegrityCryptoError, ValueError, TypeError):
        content_matches = False
        commitment_matches = False

    if not content_matches or not commitment_matches:
        result = WillIntegrityVerification.Result.MISMATCH
        chain_matches = None
        error_code = 'SNAPSHOT_OR_COMMITMENT_MISMATCH'
    elif will_record.anchor_status != AnchorStatus.CONFIRMED:
        result = WillIntegrityVerification.Result.PENDING
        chain_matches = None
        error_code = will_record.last_error_code or will_record.anchor_status
    else:
        try:
            chain_matches = verify_anchor(will_record)
            if not chain_matches and will_record.anchor_status == AnchorStatus.CONFIRMED:
                will_record.anchor_status = AnchorStatus.FAILED
                will_record.last_error_code = 'CHAIN_COMMITMENT_MISMATCH'
                will_record.save(update_fields=['anchor_status', 'last_error_code', 'updated_at'])
            result = (
                WillIntegrityVerification.Result.MATCH
                if chain_matches
                else WillIntegrityVerification.Result.MISMATCH
            )
            error_code = '' if chain_matches else 'CHAIN_COMMITMENT_MISMATCH'
        except (BlockchainConfigurationError, BlockchainUnavailable):
            chain_matches = None
            result = WillIntegrityVerification.Result.UNAVAILABLE
            error_code = 'RPC_UNAVAILABLE'

    document_results = _verify_documents(will_record)
    verification = WillIntegrityVerification.objects.create(
        will_record=will_record,
        actor=actor,
        result=result,
        content_matches=content_matches,
        chain_matches=chain_matches,
        details={
            'error_code': error_code,
            'documents': document_results,
        },
    )
    return verification

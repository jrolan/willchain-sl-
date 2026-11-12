import hashlib
import json
import os
import tempfile
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.documents.models import WillDocument
from apps.documents.storage import private_document_storage
from apps.verification.models import VerificationCase
from apps.wills.models import Will
from .crypto import (
    canonical_json,
    commitment_for,
    decrypt_secret,
    new_record_reference,
    new_salt,
    sha256_hex,
)
from .blockchain import process_anchor
from .models import AnchorStatus, DocumentIntegrityRecord, WillIntegrityRecord
from .services import create_will_integrity_record, verify_will_integrity


class IntegrityCryptoTests(SimpleTestCase):
    def test_canonical_json_ignores_object_key_order_and_whitespace(self):
        first = canonical_json({'b': [2, 1], 'a': {'y': True, 'x': None}})
        second = canonical_json({'a': {'x': None, 'y': True}, 'b': [2, 1]})

        self.assertEqual(first, second)
        self.assertEqual(sha256_hex(first), sha256_hex(second))

    def test_secure_random_salts_produce_different_commitments(self):
        reference = new_record_reference()
        digest = hashlib.sha256(b'will').hexdigest()

        first = commitment_for(reference, digest, new_salt())
        second = commitment_for(reference, digest, new_salt())

        self.assertNotEqual(first, second)
        self.assertEqual(len(bytes.fromhex(reference)), 32)


class IntegrityWorkflowTests(APITestCase):
    def setUp(self):
        self.owner = self.create_user('owner@example.com', User.Role.OWNER)
        self.other_owner = self.create_user('other@example.com', User.Role.OWNER)

    @staticmethod
    def create_user(email, role):
        return User.objects.create_user(
            email=email,
            password='Strong-password-123!',
            first_name='Test',
            last_name='User',
            role=role,
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )

    def finalized_will(self, owner=None):
        return Will.objects.create(
            owner=owner or self.owner,
            title='Private will',
            content={'beneficiaries': [{'full_name': 'Private Beneficiary'}]},
            status=Will.Status.FINALIZED,
            version=2,
            finalized_at=timezone.now(),
        )

    def test_finalization_creates_encrypted_immutable_snapshot_without_chain_access(self):
        will = Will.objects.create(
            owner=self.owner,
            title='Will',
            content={'beneficiaries': [{'full_name': 'Private Beneficiary'}]},
        )
        self.client.force_authenticate(self.owner)

        response = self.client.post(reverse('wills:will-finalize', args=[will.pk]), format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        will.refresh_from_db()
        record = WillIntegrityRecord.objects.get(will=will)
        self.assertEqual(will.status, Will.Status.FINALIZED)
        self.assertEqual(record.anchor_status, AnchorStatus.QUEUED)
        snapshot = decrypt_secret('will-snapshot', record.encrypted_snapshot)
        self.assertIn(b'"schema":"willchain-will-integrity-v1"', snapshot)
        self.assertNotIn(self.owner.email.encode(), snapshot)
        self.assertIn(b'Private Beneficiary', snapshot)
        self.assertNotIn(b'Private Beneficiary', record.encrypted_snapshot.encode())

    def test_snapshot_is_immutable_and_verification_detects_changed_will_content(self):
        will = self.finalized_will()
        record = create_will_integrity_record(will)
        original_reference = record.record_reference
        will.content = {'beneficiaries': [{'full_name': 'Changed Beneficiary'}]}
        will.save(update_fields=['content'])

        verification = verify_will_integrity(record, self.owner)

        self.assertEqual(verification.result, 'MISMATCH')
        self.assertFalse(verification.content_matches)
        record.refresh_from_db()
        self.assertEqual(record.record_reference, original_reference)
        self.assertEqual(record.anchor_status, AnchorStatus.QUEUED)

    def test_owner_status_api_does_not_expose_snapshot_or_salt(self):
        will = self.finalized_will()
        create_will_integrity_record(will)
        self.client.force_authenticate(self.owner)

        response = self.client.get(reverse('integrity:will-integrity', args=[will.pk]))
        payload = json.dumps(response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['record']['anchor_status'], AnchorStatus.QUEUED)
        self.assertNotIn('encrypted_salt', payload)
        self.assertNotIn('encrypted_snapshot', payload)
        self.assertNotIn('Private Beneficiary', payload)

    def test_owner_cannot_read_another_owners_integrity_status(self):
        will = self.finalized_will(owner=self.other_owner)
        create_will_integrity_record(will)
        self.client.force_authenticate(self.owner)

        response = self.client.get(reverse('integrity:will-integrity', args=[will.pk]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_assigned_lawyer_can_read_evidence_but_not_document_metadata(self):
        will = self.finalized_will()
        record = create_will_integrity_record(will)
        lawyer = self.create_user('lawyer@example.com', User.Role.LAWYER_VERIFIER)
        VerificationCase.objects.create(
            case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
            submission_type=VerificationCase.SubmissionType.OWNER_INITIATED,
            status=VerificationCase.Status.OPEN,
            will=will,
            initiator=self.owner,
            assigned_lawyer=lawyer,
        )
        self.client.force_authenticate(lawyer)

        response = self.client.get(reverse('integrity:lawyer-will-integrity', args=[will.pk]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['record_reference'], record.record_reference)
        self.assertEqual(response.data['data']['document_records'], [])

    def test_unassigned_lawyer_cannot_read_integrity_evidence(self):
        will = self.finalized_will()
        create_will_integrity_record(will)
        lawyer = self.create_user('unassigned@example.com', User.Role.LAWYER_VERIFIER)
        self.client.force_authenticate(lawyer)

        response = self.client.get(reverse('integrity:lawyer-will-integrity', args=[will.pk]))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_verify_and_store_a_confirmed_match(self):
        will = self.finalized_will()
        record = create_will_integrity_record(will)
        record.anchor_status = AnchorStatus.CONFIRMED
        record.save(update_fields=['anchor_status'])
        self.client.force_authenticate(self.owner)

        with patch('apps.integrity.services.verify_anchor', return_value=True):
            response = self.client.post(reverse('integrity:will-integrity', args=[will.pk]), format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['verification']['result'], 'MATCH')
        self.assertTrue(response.data['data']['verification']['chain_matches'])

    def test_missing_chain_configuration_leaves_record_retryable_and_not_confirmed(self):
        will = self.finalized_will()
        record = create_will_integrity_record(will)

        with override_settings(INTEGRITY_CONTRACT_ADDRESS='', INTEGRITY_SIGNER_PRIVATE_KEY=''):
            updated = process_anchor(record)

        self.assertEqual(updated.anchor_status, AnchorStatus.QUEUED)
        self.assertEqual(updated.last_error_code, 'CHAIN_CONFIGURATION_MISSING')

    @override_settings(INTEGRITY_NETWORK_NAME='test-chain', INTEGRITY_CHAIN_ID=31337)
    def test_finalized_document_is_hashed_from_private_bytes_and_changes_are_detected(self):
        will = self.finalized_will()
        with tempfile.TemporaryDirectory() as temporary_directory:
            private_root = Path(temporary_directory) / 'private'
            public_root = Path(temporary_directory) / 'public'
            with override_settings(PRIVATE_DOCUMENT_ROOT=private_root, MEDIA_ROOT=public_root):
                storage_key = f'{"a" * 64}.pdf'
                path = private_document_storage.root_path() / storage_key
                original_bytes = b'private supporting evidence'
                path.write_bytes(original_bytes)
                document = WillDocument.objects.create(
                    will=will,
                    document_type=WillDocument.DocumentType.OTHER,
                    original_filename='evidence.pdf',
                    storage_key=storage_key,
                    media_type='application/pdf',
                    file_size=len(original_bytes),
                    checksum_sha256=hashlib.sha256(original_bytes).hexdigest(),
                )
                will_record = create_will_integrity_record(will)
                document_record = DocumentIntegrityRecord.objects.get(document=document)
                self.assertEqual(
                    document_record.content_digest,
                    hashlib.sha256(original_bytes).hexdigest(),
                )
                document_record.anchor_status = AnchorStatus.CONFIRMED
                document_record.save(update_fields=['anchor_status'])
                path.write_bytes(b'modified evidence')

                with patch('apps.integrity.services.verify_anchor', return_value=True):
                    verification = verify_will_integrity(will_record, self.owner)

        self.assertEqual(verification.details['documents'], [
            {'document_id': document.pk, 'result': 'MISMATCH'},
        ])


@skipUnless(
    os.environ.get('RUN_HARDHAT_INTEGRATION') == '1',
    'Requires a running local Hardhat node and deployed registry.',
)
class LocalHardhatIntegrationTests(APITestCase):
    def test_django_anchors_will_and_document_and_verifies_receipts(self):
        required_environment = (
            'INTEGRITY_RPC_URL',
            'INTEGRITY_SIGNER_PRIVATE_KEY',
            'INTEGRITY_CONTRACT_ADDRESS',
        )
        self.assertTrue(all(os.environ.get(key) for key in required_environment))
        owner = User.objects.create_user(
            email='hardhat-owner@example.com',
            password='Strong-password-123!',
            first_name='Test',
            last_name='Owner',
            role=User.Role.OWNER,
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )
        will = Will.objects.create(
            owner=owner,
            title='Local Hardhat test will',
            content={'assets': ['private test asset']},
            status=Will.Status.FINALIZED,
            version=2,
            finalized_at=timezone.now(),
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            private_root = Path(temporary_directory) / 'private'
            public_root = Path(temporary_directory) / 'public'
            with override_settings(
                PRIVATE_DOCUMENT_ROOT=private_root,
                MEDIA_ROOT=public_root,
                INTEGRITY_NETWORK_NAME='hardhat-local',
                INTEGRITY_CHAIN_ID=31337,
                INTEGRITY_CONFIRMATIONS=1,
                INTEGRITY_RPC_TIMEOUT=10,
            ):
                storage_key = f'{"b" * 64}.pdf'
                path = private_document_storage.root_path() / storage_key
                contents = b'local private evidence bytes'
                path.write_bytes(contents)
                WillDocument.objects.create(
                    will=will,
                    document_type=WillDocument.DocumentType.OTHER,
                    original_filename='evidence.pdf',
                    storage_key=storage_key,
                    media_type='application/pdf',
                    file_size=len(contents),
                    checksum_sha256=hashlib.sha256(contents).hexdigest(),
                )
                will_record = create_will_integrity_record(will)
                anchored_will = process_anchor(will_record)
                document_record = will_record.document_records.get()
                anchored_document = process_anchor(document_record)

                self.assertEqual(
                    anchored_will.anchor_status,
                    AnchorStatus.CONFIRMED,
                    anchored_will.last_error_code,
                )
                self.assertEqual(anchored_document.anchor_status, AnchorStatus.CONFIRMED)
                verification = verify_will_integrity(will_record, owner)

        self.assertEqual(verification.result, 'MATCH')
        self.assertEqual(verification.details['documents'], [
            {'document_id': document_record.document_id, 'result': 'MATCH'},
        ])

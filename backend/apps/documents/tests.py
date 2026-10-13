import hashlib
import io
import tempfile
from types import ModuleType
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.conf.urls.static import static
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfWriter
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.beneficiaries.models import BeneficiaryInvitation, WillBeneficiary
from apps.wills.models import Will
from .models import DocumentIntegrityCheck, WillDocument
from .storage import PrivateStorageError, private_document_storage


def valid_pdf_content():
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


PDF_CONTENT = valid_pdf_content()


def upload_file(name='evidence.pdf', content=PDF_CONTENT, content_type='application/pdf'):
    return SimpleUploadedFile(name, content, content_type=content_type)


class WillDocumentApiTests(APITestCase):
    def setUp(self):
        self.temp_storage = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(PRIVATE_DOCUMENT_ROOT=Path(self.temp_storage.name))
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.temp_storage.cleanup)
        self.owner = self.create_user('document-owner@example.com')
        self.will = Will.objects.create(owner=self.owner, title='Private Will', content={})
        self.client.force_authenticate(self.owner)

    def create_user(self, email, **overrides):
        return User.objects.create_user(
            email=email,
            first_name='Test',
            last_name='User',
            password='Strong-password-123!',
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
            **overrides,
        )

    def upload(self, *, will=None, file=None, document_type='IDENTITY', **extra):
        return self.client.post(
            reverse('wills:will-documents', args=[(will or self.will).pk]),
            {'file': file or upload_file(), 'document_type': document_type, **extra},
            format='multipart',
        )

    def create_document(self):
        response = self.upload()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return WillDocument.objects.get(pk=response.data['data']['id'])

    def test_owner_uploads_private_file_and_downloads_through_authorized_api(self):
        response = self.upload(file=upload_file('../../evidence.pdf'))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        document = WillDocument.objects.get(pk=response.data['data']['id'])
        private_path = Path(settings.PRIVATE_DOCUMENT_ROOT) / document.storage_key
        self.assertTrue(private_path.is_file())
        self.assertNotEqual(private_path.resolve().parent, Path(settings.MEDIA_ROOT).resolve())
        self.assertEqual(document.original_filename, 'evidence.pdf')
        self.assertEqual(document.checksum_sha256, hashlib.sha256(PDF_CONTENT).hexdigest())
        self.assertNotIn('storage_key', response.data['data'])
        self.assertFalse((Path(settings.MEDIA_ROOT) / document.storage_key).exists())
        media_urlconf = ModuleType('private_document_debug_media_urls')
        with override_settings(DEBUG=True):
            media_urlconf.urlpatterns = static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
        with override_settings(ROOT_URLCONF=media_urlconf, DEBUG=True):
            public_media = self.client.get(f'{settings.MEDIA_URL}{document.storage_key}')
        self.assertEqual(public_media.status_code, status.HTTP_404_NOT_FOUND)

        download = self.client.get(reverse('wills:will-document-download', args=[self.will.pk, document.pk]))
        self.assertEqual(download.status_code, status.HTTP_200_OK)
        self.assertIn('attachment', download['Content-Disposition'].lower())
        self.assertEqual(download['Content-Type'], 'application/pdf')
        self.assertEqual(download['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(b''.join(download.streaming_content), PDF_CONTENT)

    def test_unauthenticated_and_inactive_accounts_are_rejected(self):
        self.client.force_authenticate(user=None)
        list_url = reverse('wills:will-documents', args=[self.will.pk])
        unauthenticated = [
            self.client.get(list_url),
            self.client.post(list_url, {'file': upload_file(), 'document_type': 'IDENTITY'}, format='multipart'),
        ]
        self.assertTrue(all(response.status_code == status.HTTP_401_UNAUTHORIZED for response in unauthenticated))

        self.client.force_authenticate(self.owner)
        document = self.create_document()
        self.client.force_authenticate(user=None)
        detail_url = reverse('wills:will-document-detail', args=[self.will.pk, document.pk])
        unauthenticated = [
            self.client.get(detail_url),
            self.client.patch(detail_url, {'description': 'no'}, format='json'),
            self.client.delete(detail_url),
            self.client.get(reverse('wills:will-document-download', args=[self.will.pk, document.pk])),
            self.client.post(reverse('wills:will-document-replace', args=[self.will.pk, document.pk]), {'file': upload_file()}, format='multipart'),
            self.client.get(reverse('wills:will-document-integrity', args=[self.will.pk, document.pk])),
            self.client.post(reverse('wills:will-document-integrity', args=[self.will.pk, document.pk])),
        ]
        self.assertTrue(all(response.status_code == status.HTTP_401_UNAUTHORIZED for response in unauthenticated))

        self.client.force_authenticate(self.owner)
        self.owner.account_status = User.AccountStatus.SUSPENDED
        self.owner.save(update_fields=('account_status',))
        response = self.client.get(reverse('wills:will-document-download', args=[self.will.pk, document.pk]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_other_owner_beneficiary_witness_and_lawyer_cannot_access_documents(self):
        document = self.create_document()
        for index, role in enumerate((User.Role.OWNER, User.Role.BENEFICIARY, User.Role.WITNESS, User.Role.LAWYER_VERIFIER)):
            with self.subTest(role=role):
                user = self.create_user(f'other-{index}@example.com', role=role)
                self.client.force_authenticate(user)
                detail = self.client.get(reverse('wills:will-document-detail', args=[self.will.pk, document.pk]))
                download = self.client.get(reverse('wills:will-document-download', args=[self.will.pk, document.pk]))
                self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)
                self.assertEqual(download.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(AuditEvent.objects.filter(event_type=AuditEvent.EventType.SECURITY_ALERT).exists())

    def test_other_owner_cannot_list_mutate_replace_delete_or_check_integrity(self):
        document = self.create_document()
        other_owner = self.create_user('intruder@example.com')
        self.client.force_authenticate(other_owner)
        list_response = self.client.get(reverse('wills:will-documents', args=[self.will.pk]))
        detail_url = reverse('wills:will-document-detail', args=[self.will.pk, document.pk])
        denied = [
            list_response,
            self.client.patch(detail_url, {'description': 'stolen'}, format='json'),
            self.client.delete(detail_url),
            self.client.post(
                reverse('wills:will-document-replace', args=[self.will.pk, document.pk]),
                {'file': upload_file()}, format='multipart',
            ),
            self.client.post(reverse('wills:will-document-integrity', args=[self.will.pk, document.pk])),
        ]
        self.assertTrue(all(response.status_code == status.HTTP_404_NOT_FOUND for response in denied))
        document.refresh_from_db()
        self.assertEqual(document.status, WillDocument.Status.ACTIVE)
        self.assertFalse(DocumentIntegrityCheck.objects.filter(document=document).exists())
        denied_audits = AuditEvent.objects.filter(
            event_type=AuditEvent.EventType.SECURITY_ALERT,
            details__resource='will_document',
            details__action='ACCESS_DENIED',
        )
        self.assertEqual(denied_audits.count(), 5)

    def test_client_cannot_mass_assign_protected_document_fields(self):
        response = self.upload(
            file=upload_file(),
            owner=str(self.owner.pk),
            will_id='999999',
            storage_key='../../outside.pdf',
            checksum_sha256='0' * 64,
            status='DELETED',
            version='999',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        document = WillDocument.objects.get(pk=response.data['data']['id'])
        self.assertEqual(document.will, self.will)
        self.assertEqual(document.uploaded_by, self.owner)
        self.assertEqual(document.status, WillDocument.Status.ACTIVE)
        self.assertEqual(document.version, 1)
        self.assertEqual(document.checksum_sha256, hashlib.sha256(PDF_CONTENT).hexdigest())

    def test_member_can_access_only_a_will_they_actually_own(self):
        member = self.create_user('member-owner@example.com', role=User.Role.MEMBER)
        member_will = Will.objects.create(owner=member, title='Member Will', content={})
        self.client.force_authenticate(member)
        own_response = self.client.get(reverse('wills:will-documents', args=[member_will.pk]))
        other_response = self.client.get(reverse('wills:will-documents', args=[self.will.pk]))
        self.assertEqual(own_response.status_code, status.HTTP_200_OK)
        self.assertEqual(other_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_accepted_beneficiary_relationship_does_not_grant_document_access(self):
        document = self.create_document()
        beneficiary = self.create_user('accepted-beneficiary@example.com', role=User.Role.BENEFICIARY)
        relationship = WillBeneficiary.objects.create(
            will=self.will,
            beneficiary_user=beneficiary,
            normalized_email=beneficiary.email,
            status=WillBeneficiary.Status.ACTIVE,
            accepted_at=timezone.now(),
        )
        BeneficiaryInvitation.objects.create(
            relationship=relationship,
            recipient_email=beneficiary.email,
            status=BeneficiaryInvitation.Status.ACCEPTED,
            expires_at=timezone.now(),
            responded_at=timezone.now(),
        )
        self.client.force_authenticate(beneficiary)

        response = self.client.get(reverse('wills:will-document-download', args=[self.will.pk, document.pk]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_administrator_receives_metadata_only_and_cannot_download(self):
        document = self.create_document()
        admin = self.create_user('admin@example.com', role=User.Role.ADMINISTRATOR)
        self.client.force_authenticate(admin)

        metadata = self.client.get(reverse('documents:admin-document-metadata'))
        self.assertEqual(metadata.status_code, status.HTTP_200_OK)
        serialized = str(metadata.data)
        self.assertIn(str(document.pk), serialized)
        self.assertNotIn(document.original_filename, serialized)
        self.assertNotIn(document.checksum_sha256, serialized)
        self.assertNotIn(document.storage_key, serialized)
        denied = self.client.get(reverse('wills:will-document-download', args=[self.will.pk, document.pk]))
        self.assertEqual(denied.status_code, status.HTTP_404_NOT_FOUND)

    def test_upload_rejects_unsupported_mime_signature_empty_and_oversized_content(self):
        cases = (
            upload_file('archive.zip', b'PK\x03\x04', 'application/zip'),
            upload_file('fake.jpg', PDF_CONTENT, 'image/jpeg'),
            upload_file('fake.pdf', b'%PDF-1.4 malformed', 'application/pdf'),
            upload_file('empty.pdf', b'', 'application/pdf'),
            upload_file('large.pdf', b'x' * 10_000_001, 'application/pdf'),
        )
        for file in cases:
            with self.subTest(filename=file.name):
                response = self.upload(file=file)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(WillDocument.objects.exists())

    def test_png_and_jpeg_uploads_are_validated_from_actual_image_content(self):
        from PIL import Image

        for image_format, extension, media_type in (('PNG', 'png', 'image/png'), ('JPEG', 'jpg', 'image/jpeg')):
            with self.subTest(image_format=image_format):
                stream = io.BytesIO()
                Image.new('RGB', (8, 8), color=(20, 100, 80)).save(stream, format=image_format)
                response = self.upload(file=upload_file(f'image.{extension}', stream.getvalue(), media_type))
                self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_storage_rejects_guessed_or_traversal_keys(self):
        with self.assertRaises(PrivateStorageError):
            private_document_storage.open('../../outside.pdf')

    def test_storage_refuses_public_media_root_configuration(self):
        with override_settings(PRIVATE_DOCUMENT_ROOT=settings.MEDIA_ROOT):
            with self.assertRaises(PrivateStorageError):
                private_document_storage.root_path()

    def test_draft_update_replacement_and_soft_delete_preserve_version_history(self):
        original = self.create_document()
        patch_response = self.client.patch(
            reverse('wills:will-document-detail', args=[self.will.pk, original.pk]),
            {'description': 'Verified identity evidence'},
            format='json',
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)

        replacement_response = self.client.post(
            reverse('wills:will-document-replace', args=[self.will.pk, original.pk]),
            {'file': upload_file('replacement.pdf')},
            format='multipart',
        )
        self.assertEqual(replacement_response.status_code, status.HTTP_201_CREATED, replacement_response.data)
        replacement = WillDocument.objects.get(pk=replacement_response.data['data']['id'])
        original.refresh_from_db()
        self.assertEqual(original.status, WillDocument.Status.REPLACED)
        self.assertEqual(original.replaced_by_id, replacement.pk)
        self.assertEqual(replacement.replaced_from_id, original.pk)
        self.assertEqual(replacement.version, 2)
        versions = self.client.get(reverse('wills:will-document-versions', args=[self.will.pk, original.pk]))
        self.assertEqual(len(versions.data['data']), 2)
        self.assertEqual(self.client.get(reverse('wills:will-document-download', args=[self.will.pk, original.pk])).status_code, 404)

        delete_response = self.client.delete(reverse('wills:will-document-detail', args=[self.will.pk, replacement.pk]))
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        replacement.refresh_from_db()
        self.assertEqual(replacement.status, WillDocument.Status.DELETED)
        self.assertIsNotNone(replacement.deleted_at)
        listing = self.client.get(reverse('wills:will-documents', args=[self.will.pk]))
        self.assertEqual(listing.data['data'], [])
        self.assertTrue(Path(settings.PRIVATE_DOCUMENT_ROOT, replacement.storage_key).exists())

    def test_finalized_integrity_mismatch_does_not_mutate_document_record(self):
        document = self.create_document()
        self.will.status = Will.Status.FINALIZED
        self.will.save(update_fields=('status',))
        before = {field.attname: getattr(document, field.attname) for field in document._meta.concrete_fields}
        stored_path = Path(settings.PRIVATE_DOCUMENT_ROOT, document.storage_key)
        stored_path.write_bytes(PDF_CONTENT + b'corruption')

        response = self.client.post(reverse('wills:will-document-integrity', args=[self.will.pk, document.pk]))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['data']['result'], DocumentIntegrityCheck.Result.MISMATCH)
        document.refresh_from_db()
        after = {field.attname: getattr(document, field.attname) for field in document._meta.concrete_fields}
        self.assertEqual(before, after)
        check = DocumentIntegrityCheck.objects.get(document=document)
        self.assertEqual(check.expected_checksum, before['checksum_sha256'])
        self.assertNotEqual(check.computed_checksum, check.expected_checksum)

    def test_missing_stored_file_records_safe_integrity_error(self):
        document = self.create_document()
        Path(settings.PRIVATE_DOCUMENT_ROOT, document.storage_key).unlink()

        response = self.client.post(reverse('wills:will-document-integrity', args=[self.will.pk, document.pk]))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['data']['result'], DocumentIntegrityCheck.Result.ERROR)
        self.assertEqual(response.data['data']['error_code'], 'STORAGE_UNAVAILABLE')
        document.refresh_from_db()
        self.assertEqual(document.checksum_sha256, hashlib.sha256(PDF_CONTENT).hexdigest())

    def test_finalized_will_rejects_document_mutations_but_allows_reads_and_checks(self):
        document = self.create_document()
        self.will.status = Will.Status.FINALIZED
        self.will.save(update_fields=('status',))
        detail_url = reverse('wills:will-document-detail', args=[self.will.pk, document.pk])
        before = (document.checksum_sha256, document.storage_key, document.version, document.status)

        update = self.client.patch(detail_url, {'description': 'Changed'}, format='json')
        delete = self.client.delete(detail_url)
        replace = self.client.post(
            reverse('wills:will-document-replace', args=[self.will.pk, document.pk]),
            {'file': upload_file()}, format='multipart',
        )
        self.assertEqual(update.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(delete.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(replace.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.get(detail_url).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.post(reverse('wills:will-document-integrity', args=[self.will.pk, document.pk])).status_code, 201)
        document.refresh_from_db()
        self.assertEqual((document.checksum_sha256, document.storage_key, document.version, document.status), before)

    def test_audit_failure_rolls_back_upload_and_removes_unreferenced_file(self):
        self.client.raise_request_exception = False
        with patch('apps.documents.services.record_document_audit', side_effect=RuntimeError('audit unavailable')):
            response = self.upload()

        self.assertEqual(response.status_code, 500)
        self.assertFalse(WillDocument.objects.exists())
        self.assertEqual(list(Path(settings.PRIVATE_DOCUMENT_ROOT).glob('*')), [])

    def test_archived_will_rejects_mutation_and_allows_read_only_integrity_check(self):
        document = self.create_document()
        self.will.status = Will.Status.ARCHIVED
        self.will.save(update_fields=('status',))
        update = self.client.patch(
            reverse('wills:will-document-detail', args=[self.will.pk, document.pk]),
            {'description': 'Changed'}, format='json',
        )
        self.assertEqual(update.status_code, status.HTTP_400_BAD_REQUEST)
        check = self.client.post(reverse('wills:will-document-integrity', args=[self.will.pk, document.pk]))
        self.assertEqual(check.status_code, status.HTTP_201_CREATED)

    def test_soft_deleted_document_exposes_history_but_cannot_start_new_integrity_check(self):
        document = self.create_document()
        delete_response = self.client.delete(reverse('wills:will-document-detail', args=[self.will.pk, document.pk]))
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)

        history = self.client.get(reverse('wills:will-document-integrity', args=[self.will.pk, document.pk]))
        new_check = self.client.post(reverse('wills:will-document-integrity', args=[self.will.pk, document.pk]))

        self.assertEqual(history.status_code, status.HTTP_200_OK)
        self.assertEqual(new_check.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(DocumentIntegrityCheck.objects.filter(document=document).exists())

    def test_existing_draft_will_deletion_still_cascades_document_records(self):
        document = self.create_document()
        self.client.post(reverse('wills:will-document-integrity', args=[self.will.pk, document.pk]))
        response = self.client.delete(reverse('wills:will-detail', args=[self.will.pk]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(WillDocument.objects.filter(pk=document.pk).exists())
        self.assertFalse(DocumentIntegrityCheck.objects.filter(document_id=document.pk).exists())
        self.assertTrue(AuditEvent.objects.filter(
            event_type=AuditEvent.EventType.SECURITY_ALERT,
            details__document_id=document.pk,
        ).exists())
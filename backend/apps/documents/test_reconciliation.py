import io
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.wills.models import Will
from .models import WillDocument


class ReconcilePrivateDocumentsTests(TestCase):
    def setUp(self):
        self.temp_storage = tempfile.TemporaryDirectory(prefix='willchain-reconcile-🏛️-')
        self.addCleanup(self.temp_storage.cleanup)
        self.storage_root = Path(self.temp_storage.name) / 'private-documents-🏛️'
        self.settings_override = override_settings(PRIVATE_DOCUMENT_ROOT=self.storage_root)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.storage_root.mkdir(parents=True)
        self.owner = User.objects.create_user(
            email='reconcile-owner@example.com',
            first_name='Test',
            last_name='Owner',
            password='Strong-password-123!',
            account_status=User.AccountStatus.ACTIVE,
        )
        self.will = Will.objects.create(owner=self.owner, title='Reconciliation Will', content={})

    def make_key(self, character):
        return f'{character * 64}.pdf'

    def create_file(self, key, *, age_hours=None, root=None):
        directory = Path(root or self.storage_root)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / key
        path.write_bytes(b'private document test bytes')
        if age_hours is not None:
            old_time = time.time() - age_hours * 3600
            os.utime(path, (old_time, old_time))
        return path

    def create_document_reference(self, key, status, *, deleted_at=None):
        return WillDocument.objects.create(
            will=self.will,
            document_type=WillDocument.DocumentType.OTHER,
            original_filename='retained.pdf',
            storage_key=key,
            media_type='application/pdf',
            file_size=27,
            checksum_sha256='a' * 64,
            status=status,
            deleted_at=deleted_at,
            deleted_by=self.owner if deleted_at else None,
        )

    def run_command(self, *args, **kwargs):
        output = io.StringIO()
        call_command('reconcile_private_documents', *args, stdout=output, **kwargs)
        return output.getvalue()

    def test_default_dry_run_reports_orphan_without_deleting_it(self):
        orphan = self.create_file(self.make_key('b'), age_hours=25)

        output = self.run_command()

        self.assertIn(orphan.name, output)
        self.assertIn('Dry run', output)
        self.assertIn('No files deleted', output)
        self.assertTrue(orphan.exists())
        self.assertNotIn(str(self.storage_root), output)

    def test_active_and_soft_deleted_document_files_are_never_orphans(self):
        active_key = self.make_key('c')
        deleted_key = self.make_key('d')
        active_file = self.create_file(active_key, age_hours=30)
        deleted_file = self.create_file(deleted_key, age_hours=30)
        self.create_document_reference(active_key, WillDocument.Status.ACTIVE)
        self.create_document_reference(
            deleted_key,
            WillDocument.Status.DELETED,
            deleted_at=timezone.now(),
        )

        output = self.run_command('--apply')

        self.assertIn('Removed 0', output)
        self.assertTrue(active_file.exists())
        self.assertTrue(deleted_file.exists())

    def test_recent_orphan_is_protected_by_age_threshold(self):
        recent = self.create_file(self.make_key('e'))

        output = self.run_command('--apply', min_age_hours=1)

        self.assertIn('Removed 0', output)
        self.assertTrue(recent.exists())

    def test_eligible_orphan_is_deleted_only_with_explicit_apply(self):
        orphan = self.create_file(self.make_key('f'), age_hours=25)

        dry_run = self.run_command(min_age_hours=1)
        self.assertTrue(orphan.exists())
        self.assertIn(orphan.name, dry_run)

        applied = self.run_command('--apply', min_age_hours=1)
        self.assertFalse(orphan.exists())
        self.assertIn('Removed 1', applied)

    def test_apply_refuses_candidate_paths_outside_configured_private_root(self):
        outside_root = Path(self.temp_storage.name) / 'outside'
        outside_file = self.create_file(self.make_key('1'), age_hours=30, root=outside_root)

        with patch('apps.documents.storage.private_document_storage.candidate_files', return_value=iter([outside_file])):
            with self.assertRaises(CommandError):
                self.run_command('--apply', min_age_hours=1)

        self.assertTrue(outside_file.exists())

    def test_unicode_storage_path_is_safe_for_legacy_console_encoding(self):
        orphan = self.create_file(self.make_key('2'), age_hours=30)
        encoded_output = io.BytesIO()
        console = io.TextIOWrapper(encoded_output, encoding='cp1252')

        call_command('reconcile_private_documents', stdout=console)
        console.flush()
        output = encoded_output.getvalue().decode('cp1252')

        self.assertIn(orphan.name, output)
        self.assertNotIn(str(self.storage_root), output)
        self.assertTrue(orphan.exists())

    def test_filesystem_failures_produce_a_management_command_error(self):
        non_directory_parent = Path(self.temp_storage.name) / 'not-a-directory'
        non_directory_parent.write_text('blocker')
        with override_settings(PRIVATE_DOCUMENT_ROOT=non_directory_parent / 'storage'):
            with self.assertRaises(CommandError):
                self.run_command()

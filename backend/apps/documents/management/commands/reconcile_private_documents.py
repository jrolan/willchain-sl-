import time
import math

from django.core.management.base import BaseCommand, CommandError

from apps.documents.models import WillDocument
from apps.documents.storage import PrivateStorageError, private_document_storage


class Command(BaseCommand):
    help = 'Report or remove old private document files that are not referenced by document records.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Delete eligible orphan files; default is report-only.')
        parser.add_argument('--min-age-hours', type=float, default=24, help='Minimum age before a file is eligible (default: 24).')

    @staticmethod
    def _safe_output(text, stream):
        encoding = getattr(stream, 'encoding', None) or 'ascii'
        return text.encode(encoding, errors='backslashreplace').decode(encoding)

    def _filesystem_error(self, action, filename, error):
        description = error.strerror or 'filesystem operation failed'
        message = f'Unable to {action} private document file {filename} (error {error.errno}: {description}).'
        return CommandError(self._safe_output(message, self.stderr))

    def handle(self, *args, **options):
        min_age_hours = options['min_age_hours']
        if not math.isfinite(min_age_hours) or min_age_hours < 1:
            raise CommandError('--min-age-hours must be at least 1 to avoid racing active uploads.')

        try:
            root = private_document_storage.root_path()
        except PrivateStorageError as error:
            raise CommandError(self._safe_output(f'Private document storage is unavailable: {error}', self.stderr)) from error
        except OSError as error:
            raise self._filesystem_error('open storage for', '[private root]', error) from error

        referenced = set(WillDocument.objects.values_list('storage_key', flat=True))
        cutoff = time.time() - min_age_hours * 3600
        candidates = []
        try:
            for path in private_document_storage.candidate_files():
                try:
                    resolved_path = path.resolve(strict=True)
                except OSError as error:
                    raise self._filesystem_error('inspect', path.name, error) from error
                if resolved_path.parent != root:
                    raise CommandError('Refusing to reconcile a file outside the private document storage root.')
                if path.name in referenced:
                    continue
                if path.stat().st_mtime <= cutoff:
                    candidates.append(path)
        except OSError as error:
            raise self._filesystem_error('inspect', '[private storage entry]', error) from error

        if not options['apply']:
            self.stdout.write(self._safe_output(f'Dry run: {len(candidates)} unreferenced file(s) eligible in private storage.', self.stdout))
            for path in candidates:
                self.stdout.write(self._safe_output(f'  {path.name}', self.stdout))
            self.stdout.write(self._safe_output('No files deleted. Re-run with --apply to remove these files.', self.stdout))
            return

        for path in candidates:
            try:
                path.unlink()
            except OSError as error:
                raise self._filesystem_error('remove', path.name, error) from error
        message = self.style.SUCCESS(f'Removed {len(candidates)} old unreferenced private file(s).')
        self.stdout.write(self._safe_output(message, self.stdout))
import time

from django.core.management.base import BaseCommand, CommandError

from apps.documents.models import WillDocument
from apps.documents.storage import private_document_storage


class Command(BaseCommand):
    help = 'Report or remove old private document files that are not referenced by document records.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Delete eligible orphan files; default is report-only.')
        parser.add_argument('--min-age-hours', type=float, default=24, help='Minimum age before a file is eligible (default: 24).')

    def handle(self, *args, **options):
        min_age_hours = options['min_age_hours']
        if min_age_hours < 1:
            raise CommandError('--min-age-hours must be at least 1 to avoid racing active uploads.')

        root = private_document_storage.root_path()
        referenced = set(WillDocument.objects.values_list('storage_key', flat=True))
        cutoff = time.time() - min_age_hours * 3600
        candidates = []
        for path in private_document_storage.candidate_files():
            if path.name in referenced or path.stat().st_mtime > cutoff:
                continue
            candidates.append(path)

        if not options['apply']:
            self.stdout.write(f'Dry run: {len(candidates)} unreferenced file(s) eligible under {root}.')
            for path in candidates:
                self.stdout.write(f'  {path.name}')
            self.stdout.write('No files deleted. Re-run with --apply to remove these files.')
            return

        for path in candidates:
            path.unlink()
        self.stdout.write(self.style.SUCCESS(f'Removed {len(candidates)} old unreferenced private file(s).'))
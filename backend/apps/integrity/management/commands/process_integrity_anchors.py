import time

from django.core.management.base import BaseCommand, CommandError

from apps.integrity.blockchain import process_anchor, reset_stale_submissions
from apps.integrity.models import AnchorStatus, DocumentIntegrityRecord, WillIntegrityRecord


class Command(BaseCommand):
    help = 'Process queued will and document integrity blockchain anchors.'

    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true', help='Continue polling for new anchors.')
        parser.add_argument('--interval', type=int, default=15, help='Polling interval in seconds with --loop.')

    def handle(self, *args, **options):
        interval = options['interval']
        if options['loop'] and interval < 1:
            raise CommandError('--interval must be at least one second.')
        while True:
            reset_stale_submissions()
            pending = []
            for model in (WillIntegrityRecord, DocumentIntegrityRecord):
                pending.extend(model.objects.filter(
                    anchor_status__in=(AnchorStatus.QUEUED, AnchorStatus.SUBMITTED),
                ).order_by('created_at'))
            for record in pending:
                    previous_state = (
                        record.anchor_status,
                        record.last_error_code,
                        record.transaction_hash,
                        record.confirmations,
                    )
                    updated = process_anchor(record)
                    current_state = (
                        updated.anchor_status,
                        updated.last_error_code,
                        updated.transaction_hash,
                        updated.confirmations,
                    )
                    if current_state != previous_state:
                        self.stdout.write(
                            f'{record._meta.model_name} {record.record_reference}: '
                            f'{updated.anchor_status} {updated.last_error_code}'.rstrip()
                        )
            if not options['loop']:
                break
            time.sleep(interval)

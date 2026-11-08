from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.verification.models import BeneficiaryNotificationOutbox
from apps.verification.services import dispatch_beneficiary_notification


class Command(BaseCommand):
    help = 'Send pending beneficiary release notifications and retry eligible failures.'

    def handle(self, *args, **options):
        now = timezone.now()
        eligible = BeneficiaryNotificationOutbox.objects.filter(
            Q(
                status__in=[
                    BeneficiaryNotificationOutbox.Status.PENDING,
                    BeneficiaryNotificationOutbox.Status.FAILED,
                ],
                available_at__lte=now,
            )
            | Q(
                status=BeneficiaryNotificationOutbox.Status.PROCESSING,
                updated_at__lt=now - timedelta(minutes=10),
            )
        ).order_by('created_at').values_list('pk', flat=True)[:100]

        attempted = delivered = 0
        for outbox_id in eligible:
            attempted += 1
            if dispatch_beneficiary_notification(outbox_id):
                delivered += 1
        self.stdout.write(f'Attempted {attempted} notification(s); delivered {delivered}.')
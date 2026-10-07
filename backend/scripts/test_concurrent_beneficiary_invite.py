import os
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.db import close_old_connections, connection
from django.test.utils import override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.beneficiaries.models import BeneficiaryInvitation, WillBeneficiary
from apps.wills.models import Will


def run_test():
    if connection.vendor != 'postgresql':
        raise RuntimeError(f"Expected PostgreSQL, got {connection.vendor!r}")

    identifier = uuid.uuid4().hex
    owner = User.objects.create_user(
        email=f'concurrency-{identifier}@example.test',
        password='Temporary-Test-Password-934!',
        first_name='Concurrency',
        last_name='Test',
        account_status=User.AccountStatus.ACTIVE,
        email_verified=True,
        role=User.Role.OWNER,
    )
    will = Will.objects.create(owner=owner, title='Concurrency Test Will', content={})
    access_token = str(RefreshToken.for_user(owner).access_token)
    payload = {
        'recipient_email': f'beneficiary-{identifier}@example.test',
        'relationship_type': 'PRIMARY',
        'full_name': 'Concurrency Beneficiary',
    }
    endpoint = reverse('beneficiaries:will-beneficiaries', args=[will.pk])
    barrier = threading.Barrier(2)

    def submit_invitation():
        close_old_connections()
        try:
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
            barrier.wait(timeout=15)
            response = client.post(endpoint, payload, format='json', HTTP_HOST='localhost')
            return response.status_code
        finally:
            close_old_connections()

    try:
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(lambda _: submit_invitation(), range(2)))

        relationships = WillBeneficiary.objects.filter(will=will, normalized_email=payload['recipient_email'])
        invitations = BeneficiaryInvitation.objects.filter(relationship__will=will)
        created_audits = AuditEvent.objects.filter(
            actor=owner,
            details__event='beneficiary_created',
            details__will_id=will.pk,
        ).count()

        print(f'DB Engine: {connection.settings_dict["ENGINE"]}')
        print(f'HTTP status codes: {sorted(results)}')
        print(f'Matching relationships: {relationships.count()}')
        print(f'Invitation attempts: {invitations.count()}')
        print(f'Beneficiary-created audit rows: {created_audits}')

        assert results.count(201) == 1, f'Expected exactly one 201 response, got {results}'
        assert all(code in (201, 400, 409) for code in results), f'Unexpected response codes: {results}'
        assert relationships.count() == 1, 'Expected exactly one relationship'
        assert invitations.count() == 1, 'Expected exactly one invitation'
        assert created_audits == 1, 'Expected exactly one creation audit'
        print('PASS: concurrent duplicate beneficiary invitation was serialized safely.')
    finally:
        AuditEvent.objects.filter(actor=owner, details__will_id=will.pk).delete()
        will.delete()
        owner.delete()


if __name__ == '__main__':
    run_test()

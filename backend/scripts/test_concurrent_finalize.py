import os
import sys
from pathlib import Path
import threading

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from rest_framework.test import APIClient
from django.urls import reverse
from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.wills.models import Will
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import connection

def run_stress_test():
    owner = User.objects.create_user(
        email='concurrent_audit_test@example.com',
        password='Password-123!',
        first_name='Concurrent',
        last_name='Tester',
        account_status=User.AccountStatus.ACTIVE,
        email_verified=True,
        role=User.Role.OWNER,
    )
    will = Will.objects.create(owner=owner, title='Concurrent Draft Will', content={'test': 'data'})
    token = str(RefreshToken.for_user(owner).access_token)

    results = []
    lock = threading.Lock()

    def send_finalize():
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = client.post(reverse('wills:will-finalize', args=[will.pk]), HTTP_HOST='localhost')
        with lock:
            results.append(res.status_code)

    threads = [threading.Thread(target=send_finalize) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    will.refresh_from_db()
    audit_count = AuditEvent.objects.filter(
        event_type=AuditEvent.EventType.WILL_FINALIZED,
        details__will_id=will.pk,
    ).count()

    print('=== CONCURRENT FINALIZATION STRESS TEST RESULTS ===')
    print(f"DB Engine: {connection.settings_dict['ENGINE']}")
    print(f"200 OK Responses: {results.count(200)}")
    print(f"400 Bad Request Responses: {results.count(400)}")
    print(f"Final Will Status: {will.status}")
    print(f"Final Will Version: {will.version}")
    print(f"WILL_FINALIZED Audit Rows: {audit_count}")

    assert results.count(200) == 1, f"Expected exactly 1 200 response, got {results.count(200)}"
    assert results.count(400) == 19, f"Expected exactly 19 400 responses, got {results.count(400)}"
    assert will.status == Will.Status.FINALIZED
    assert will.version == 2
    assert audit_count == 1, f"Expected exactly 1 audit row, got {audit_count}"
    print('PASS: Concurrency row-locking verified successfully.')

if __name__ == '__main__':
    run_stress_test()

import os
import sys
import threading
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django

django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection
from django.urls import reverse
from pypdf import PdfWriter
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.documents.storage import private_document_storage
from apps.documents.models import WillDocument
from apps.wills.models import Will


def make_valid_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    from io import BytesIO

    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def run_test(iterations=10):
    if connection.vendor != 'postgresql':
        raise SystemExit('This race test requires PostgreSQL; SQLite does not provide the required row locks.')

    suffix = uuid.uuid4().hex
    owner = User.objects.create_user(
        email=f'document-race-{suffix}@example.com',
        password='Password-123!',
        first_name='Document',
        last_name='Race',
        account_status=User.AccountStatus.ACTIVE,
        email_verified=True,
        role=User.Role.OWNER,
    )
    token = str(RefreshToken.for_user(owner).access_token)
    upload_wins = 0
    finalize_wins = 0

    try:
        for index in range(iterations):
            will = Will.objects.create(owner=owner, title=f'Concurrent Will {index}', content={})
            barrier = threading.Barrier(2)
            results = {}
            result_lock = threading.Lock()

            def send_finalize():
                close_old_connections()
                try:
                    client = APIClient()
                    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
                    barrier.wait()
                    response = client.post(reverse('wills:will-finalize', args=[will.pk]), HTTP_HOST='localhost')
                    with result_lock:
                        results['finalize'] = response.status_code
                except Exception as error:
                    with result_lock:
                        results['finalize_error'] = repr(error)
                finally:
                    close_old_connections()

            def send_upload():
                close_old_connections()
                try:
                    client = APIClient()
                    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
                    barrier.wait()
                    upload = SimpleUploadedFile('evidence.pdf', make_valid_pdf(), content_type='application/pdf')
                    response = client.post(
                        reverse('wills:will-documents', args=[will.pk]),
                        {'file': upload, 'document_type': 'IDENTITY'},
                        format='multipart',
                        HTTP_HOST='localhost',
                    )
                    with result_lock:
                        results['upload'] = response.status_code
                        results['document_id'] = response.data.get('data', {}).get('id') if response.status_code == 201 else None
                except Exception as error:
                    with result_lock:
                        results['upload_error'] = repr(error)
                finally:
                    close_old_connections()

            threads = [threading.Thread(target=send_finalize), threading.Thread(target=send_upload)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            if 'finalize_error' in results or 'upload_error' in results:
                raise AssertionError(f'Concurrent request failed: {results}')
            if results.get('finalize') != 200:
                raise AssertionError(f'Finalization did not succeed exactly once: {results}')

            will.refresh_from_db()
            if will.status != Will.Status.FINALIZED:
                raise AssertionError(f'Will was not finalized: {will.status}')
            documents = list(WillDocument.objects.filter(will=will))
            if results.get('upload') == 201:
                if len(documents) != 1 or documents[0].pk != results.get('document_id'):
                    raise AssertionError(f'Successful upload was not persisted as one version: {results}')
                if documents[0].created_at > will.finalized_at:
                    raise AssertionError('Upload committed after finalization completed.')
                upload_wins += 1
            elif results.get('upload') == 400:
                if documents:
                    raise AssertionError(f'Upload rejected but document exists: {results}')
                finalize_wins += 1
            else:
                raise AssertionError(f'Unexpected upload result: {results}')

            for document in documents:
                private_document_storage.delete(document.storage_key)
            will.delete()

        print(f'Database engine: {connection.settings_dict["ENGINE"]}')
        print(f'Iterations: {iterations}')
        print(f'Upload acquired draft lock first: {upload_wins}')
        print(f'Finalization acquired lock first: {finalize_wins}')
        print('PASS: No document mutation committed after finalization.')
    finally:
        Will.objects.filter(owner=owner).delete()
        owner.delete()


if __name__ == '__main__':
    run_test()
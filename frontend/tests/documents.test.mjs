import test from 'node:test';
import assert from 'node:assert/strict';

import {
  DOCUMENT_MAX_BYTES,
  documentErrorMessage,
  documentLifecycleRules,
  integrityResultMessage,
  validateDocumentFile,
} from '../lib/document-rules.mjs';
import { createDocumentService } from '../services/document-service-core.mjs';

test('client document validation allows only PDF, JPEG, and PNG extensions', () => {
  for (const name of ['will.pdf', 'photo.jpg', 'photo.jpeg', 'record.png']) {
    assert.equal(validateDocumentFile({ name, size: 1 }), '');
  }
  for (const name of ['record.docx', 'image.svg', 'archive.zip', 'no-extension']) {
    assert.notEqual(validateDocumentFile({ name, size: 1 }), '');
  }
});

test('client size validation uses the exact 10,000,000-byte limit', () => {
  assert.equal(DOCUMENT_MAX_BYTES, 10_000_000);
  assert.equal(validateDocumentFile({ name: 'evidence.pdf', size: 10_000_000 }), '');
  assert.equal(validateDocumentFile({ name: 'evidence.pdf', size: 10_000_001 }), 'The file exceeds the 10000000 byte limit.');
});

test('document lifecycle permits mutations only for drafts and checks on all will states', () => {
  assert.deepEqual(documentLifecycleRules('DRAFT'), {
    canMutate: true,
    canCheckIntegrity: true,
    isReadOnly: false,
  });
  for (const status of ['FINALIZED', 'ARCHIVED']) {
    assert.deepEqual(documentLifecycleRules(status), {
      canMutate: false,
      canCheckIntegrity: true,
      isReadOnly: true,
    });
  }
});

test('integrity result messages preserve rather than imply rewriting the accepted checksum', () => {
  assert.match(integrityResultMessage('VALID'), /original checksum is unchanged/i);
  assert.match(integrityResultMessage('MISMATCH'), /original checksum is retained/i);
  assert.match(integrityResultMessage('ERROR'), /original checksum is unchanged/i);
});

test('document API adapter uses owner-scoped routes and FormData for uploads', async () => {
  const calls = [];
  const apiRequest = async (path, init) => {
    calls.push({ kind: 'request', path, init });
    return { data: [] };
  };
  const expectedBlob = new Blob(['private file'], { type: 'application/pdf' });
  const apiDownload = async (path) => {
    calls.push({ kind: 'download', path });
    return expectedBlob;
  };
  const service = createDocumentService(apiRequest, apiDownload);
  const file = new Blob(['pdf content'], { type: 'application/pdf' });

  await service.getWillDocuments(17);
  await service.uploadWillDocument(17, file, 'IDENTITY', 'Evidence');
  await service.updateWillDocument(17, 4, { description: 'Updated' });
  const downloaded = await service.downloadWillDocument(17, 4);

  assert.equal(calls[0].path, '/wills/17/documents/');
  assert.equal(calls[1].path, '/wills/17/documents/');
  assert.equal(calls[1].init.method, 'POST');
  assert.ok(calls[1].init.body instanceof FormData);
  assert.equal(calls[1].init.body.get('document_type'), 'IDENTITY');
  assert.equal(calls[2].init.method, 'PATCH');
  assert.equal(calls[3].path, '/wills/17/documents/4/download/');
  assert.equal(downloaded, expectedBlob);
});

test('document API adapter propagates authorization and network failures for UI handling', async () => {
  const service = createDocumentService(
    async () => { throw new Error('Access denied.'); },
    async () => { throw new Error('Network unavailable.'); },
  );

  await assert.rejects(service.getWillDocuments(17), /Access denied/);
  await assert.rejects(service.downloadWillDocument(17, 4), /Network unavailable/);
  assert.equal(documentErrorMessage(new Error('Upload rejected.')), 'Upload rejected.');
  assert.equal(documentErrorMessage('unexpected'), 'The document request could not be completed.');
});
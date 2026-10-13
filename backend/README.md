# WillChain SL Backend

This folder will contain the Django REST Framework backend.

## Intended layout

- `config/` — Django project configuration and global settings.
- `apps/` — domain modules, each with isolated business responsibilities.
- `tests/` — cross-module integration and security tests.
- `requirements/` — dependency definitions for development and production.

## Planned domain modules

- `accounts` — identity, authentication, roles, account status, and baseline permissions.
- `wills` — will drafts, versions, finalisation, and lifecycle.
- `beneficiaries` — beneficiary relationships and allocation instructions.
- `documents` — private document metadata and storage integration.
- `verification` — post-death verification workflow and human decisions.
- `integrity` — cryptographic-hash and blockchain-reference integration.
- `ai_services` — interfaces to future OCR/AI assistance only.
- `notifications` — authorised messages and delivery status.
- `audit` — security and business-event audit records.

No private will content, credentials, API keys, or blockchain keys belong in this repository.

## Module 2: Will Management

The current will-management API is available under `/api/v1/wills/` and requires an active JWT-authenticated will owner:

- `GET /api/v1/wills/` — list the authenticated owner's wills.
- `POST /api/v1/wills/` — create a draft; ownership is assigned by the server.
- `GET /api/v1/wills/<id>/` — retrieve an owned will.
- `PATCH /api/v1/wills/<id>/` — update an eligible draft and increment its version.
- `DELETE /api/v1/wills/<id>/` — delete an eligible draft.
- `POST /api/v1/wills/<id>/finalize/` — finalize an owned draft once.

Finalized wills cannot be edited, deleted, or finalized again. Ownership is enforced at the API object-permission layer, and create, access, update, finalization, and denied-access events are recorded in the audit log without storing private will content.

Blockchain registration and AI analysis are intentionally excluded from Module 2 and belong to later modules.

## Module 4: Private documents

The document API is mounted under `/api/v1/wills/<will_id>/documents/`. Only an active authenticated owner of that specific will can access document content. Administrators have a separate metadata-only endpoint at `/api/v1/admin/documents/metadata/`. Beneficiary, witness, lawyer/verifier, and global roles do not grant content access.

Uploads accept PDF, JPEG, and PNG only, with a 10,000,000-byte (10 MB decimal) maximum. Files are validated server-side, assigned random internal names, and stored under `PRIVATE_DOCUMENT_ROOT`, which defaults to `backend/private_documents` and is not served by Django's `/media/` route. Production deployments must set this to durable private storage with restrictive access. The Docker Compose development stack mounts the named `willchain_private_documents` volume at `/app/private_documents`; do not mount this directory as public/static content.

Database updates and required audit records share a transaction. New files are staged before metadata changes and removed on ordinary transaction/audit failures. Filesystem and database transactions cannot be made atomic together, so rare process termination or cleanup I/O failure can leave an unreferenced file. Inspect candidates with `python manage.py reconcile_private_documents`; removal requires the explicit `--apply` option and files must be at least 24 hours old. The command never removes files referenced by document-version records. Soft-deleted and replaced files remain retained for history.

Integrity checks store their outcomes separately from document metadata. A mismatch preserves the accepted SHA-256 checksum; it is not evidence of who changed a file or when.

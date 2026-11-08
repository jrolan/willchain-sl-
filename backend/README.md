# WillChain SL Backend

This folder contains the Django REST Framework backend.

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

## Google sign-in and beneficiary releases

Create an OAuth 2.0 **Web application** client in Google Cloud Console. Add `http://localhost:3000` (and your deployed frontend origin) under **Authorized JavaScript origins**. This app posts Google Identity Services ID tokens to Django, so no redirect URI is required for this flow.

Use the same Google client ID in `GOOGLE_OAUTH2_CLIENT_ID` in `backend/.env` and `NEXT_PUBLIC_GOOGLE_OAUTH2_CLIENT_ID` in `frontend/.env.local`. The client ID is public; do not put a client secret in frontend code. For Docker Compose, set the public ID in the PowerShell environment before building: `$env:NEXT_PUBLIC_GOOGLE_OAUTH2_CLIENT_ID = '<your-client-id>'`, then run `docker compose up --build`. The frontend value is embedded at build time. The backend requires `google-auth` and rejects tokens it cannot verify. New Google-first accounts use the normal default OWNER role, remain pending email verification, and receive no application JWT until eligible. Existing account roles are preserved.

For live release email, set `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS` or `EMAIL_USE_SSL`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and `DEFAULT_FROM_EMAIL` in `backend/.env`. Example Gmail SMTP uses `smtp.gmail.com`, port `587`, and TLS; use a Google App Password (with 2-Step Verification), not your normal account password. Other SMTP providers can use their host and credentials. Never commit `.env` or paste secrets into chat. The console backend is blocked for release notifications because it prints claim links.

Beneficiary relationship creation and editing do not send invitations or notifications. Owners record allocations on draft wills; the assigned active lawyer reviews each allocation during a post-death verification case. After approval, that lawyer explicitly authorizes selected verified allocations. Each release has its own hashed, expiring claim token and one outbox notification. A failed email does not revoke the release. Run `python manage.py send_beneficiary_notifications` on a scheduler to deliver pending notifications and retry due failures.

The Django console email backend is intentionally not accepted as successful beneficiary-release delivery because it prints the raw claim link. Configure a non-console provider backend before enabling release notifications in a deployed environment.

Only the assigned active lawyer may authorize selected allocations on the approved case. Do not treat verification approval alone as release authorization.

## Module 4: Private documents

The document API is mounted under `/api/v1/wills/<will_id>/documents/`. Only an active authenticated owner of that specific will can access document content. Administrators have a separate metadata-only endpoint at `/api/v1/admin/documents/metadata/`. Beneficiary, witness, lawyer/verifier, and global roles do not grant content access.

Uploads accept PDF, JPEG, and PNG only, with a 10,000,000-byte (10 MB decimal) maximum. Files are validated server-side, assigned random internal names, and stored under `PRIVATE_DOCUMENT_ROOT`, which defaults to `backend/private_documents` and is not served by Django's `/media/` route. Production deployments must set this to durable private storage with restrictive access. The Docker Compose development stack mounts the named `willchain_private_documents` volume at `/app/private_documents`; do not mount this directory as public/static content.

Database updates and required audit records share a transaction. New files are staged before metadata changes and removed on ordinary transaction/audit failures. Filesystem and database transactions cannot be made atomic together, so rare process termination or cleanup I/O failure can leave an unreferenced file. Inspect candidates with `python manage.py reconcile_private_documents`; removal requires the explicit `--apply` option and files must be at least 24 hours old. The command never removes files referenced by document-version records. Soft-deleted and replaced files remain retained for history.

Integrity checks store their outcomes separately from document metadata. A mismatch preserves the accepted SHA-256 checksum; it is not evidence of who changed a file or when.

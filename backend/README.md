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

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

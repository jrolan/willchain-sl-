# WillChain SL

Secure digital will-management academic project for Sierra Leone.

The repository contains a Next.js frontend and a Django REST Framework backend. Authentication, will management, verification, lawyer review, audit, and beneficiary release workflows are implemented incrementally under the approved architecture.

Will management covers private owner drafts, lifecycle state, versioning, finalization, object-level authorization, audit events, and the authenticated owner dashboard. Beneficiary allocations are stored separately from will content, and notification is gated behind case approval, per-allocation lawyer review, and explicit release authorization. Blockchain integrity and AI services are reserved for later modules.

## Local Docker setup

Copy the backend environment template to `backend/.env` and set the local PostgreSQL password and Django secret. For a Docker Google sign-in demo, also set `NEXT_PUBLIC_GOOGLE_OAUTH2_CLIENT_ID` in the PowerShell session before building the frontend image:

```cmd
copy backend\.env.example backend\.env
set NEXT_PUBLIC_GOOGLE_OAUTH2_CLIENT_ID=your-google-oauth-web-client-id
docker compose up --build
```

The Google client ID is public and must match `GOOGLE_OAUTH2_CLIENT_ID` in `backend/.env`. See [backend/README.md](backend/README.md) for Google Cloud origins and SMTP release-email setup. In PowerShell, use `$env:NEXT_PUBLIC_GOOGLE_OAUTH2_CLIENT_ID = 'your-google-oauth-web-client-id'` instead of `set`.

The services are available at:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000/api/v1/`
- PostgreSQL: `localhost:5432`

Stop the stack with:

```cmd
docker compose down
```

The database volume is preserved between restarts. Remove it only when you intentionally want to delete local database data:

```cmd
docker compose down -v
```

## Security Audit, Limitations & Future Work

### Module 2 Security Audit Status
Module 2 (Will Management) passed comprehensive security testing, including:
- 59 automated test cases covering authentication, ownership, role isolation, anti-enumeration IDOR defense, and payload validation.
- Concurrency verification via 20-thread row-locking stress test against PostgreSQL (`backend/scripts/test_concurrent_finalize.py`).
- 100 KB payload size limit and 10-level JSON depth limits on both create and update operations.

### Limitations & Future Work
1. **Plaintext Content At Rest:** Will drafts and finalized JSON documents are stored as standard JSONB in PostgreSQL. Field-level or client-side envelope encryption will be integrated in subsequent modules.
2. **Production HTTPS & HSTS Hardening:** Production deployment requires enabling `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `SESSION_COOKIE_SECURE`, and `CSRF_COOKIE_SECURE` behind an SSL reverse proxy.
3. **PostgreSQL in CI/CD Matrix:** CI test runners should execute regression suites against containerized PostgreSQL alongside unit tests.
4. **Rate Limiting & Throttling:** Specialized endpoint throttling for will creation and finalization to complement platform-wide IP/user throttles.

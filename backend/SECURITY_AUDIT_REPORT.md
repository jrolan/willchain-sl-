# Independent Implementation Review & Security Audit — WillChain SL

**Audit date:** 2026-11-08
**Auditor:** Kilo
**Mode:** Independent re-audit (source review + tests + fixes)

---

## 1. Actual Working-Tree Changes Baseline (for this audit)

Modified (staged or unstaged):

Backend:
- `backend/.env.example`
- `backend/README.md`
- `backend/docker-compose.yml`
- `backend/requirements/base.txt`
- `backend/config/settings.py`
- `backend/apps/accounts/{models,serializers,services,tests,urls,views}.py`
- `backend/apps/audit/models.py`
- `backend/apps/beneficiaries/{models,serializers,services,tests,urls,views}.py`
- `backend/apps/verification/{models,permissions,serializers,services,tests,urls,views}.py`
- `backend/apps/wills/{serializers,tests,urls,views}.py`

Frontend:
- `frontend/Dockerfile`
- `frontend/README.md`
- `frontend/.env.example`
- `frontend/app/dashboard/verification/page.tsx`
- `frontend/app/login/page.tsx`
- `frontend/app/register/page.tsx`
- `frontend/app/verify-account/page.tsx`
- `frontend/components/beneficiaries/will-beneficiary-manager.tsx`
- `frontend/components/layout/dashboard-shell.tsx`
- `frontend/lib/auth-context.tsx`
- `frontend/services/auth-service.ts`
- `frontend/services/beneficiary-service.ts`
- `frontend/services/verification-service.ts`
- `frontend/types/{beneficiaries,verification,wills}.ts`

Untracked:
- `backend/SUPERVISOR_WORKFLOW_REVISION_ARCHITECTURE.md`
- `backend/apps/accounts/migrations/0006_user_google_sub.py`
- `backend/apps/audit/migrations/0006_alter_auditevent_event_type.py`
- `backend/apps/beneficiaries/migrations/0002_beneficiaryallocation.py`
- `backend/apps/verification/management/`
- `backend/apps/verification/migrations/0002_beneficiaryrelease_outbox.py`
- `frontend/.env.example`
- `frontend/app/beneficiary/`
- `frontend/app/dashboard/beneficiary-allocations/`
- `frontend/components/auth/google-sign-in-button.tsx`

---

## 2. Security / Implementation Verification RESULTS

### 2.1 Google Authentication — VERIFIED ✅
- `apps/accounts/services.py::verify_google_id_token`
- Uses `google.oauth2.id_token.verify_oauth2_token` with `google.auth.transport.requests.Request()`, `clock_skew_in_seconds=10`.
- Rejects missing token/client_id; rejects unverified email; validates `sub` + `email`.
- Login flow: 400 invalid request, 401 invalid token, 400 missing identity, 400 unverified email, 409 conflict, 401 inactive — all consistent.
- Refresh token rotation + blacklist enabled (SimpleJWT).
- Refresh cookie: HttpOnly, secure (env, default True when not DEBUG), SameSite=Lax, path-scoped, 7-day max age.

### 2.2 LAWYER READ-ONLY ACCESS — VERIFIED ✅
- `LawyerWillViewAPIView` → `IsAssignedLawyerOnAuthorizedCase`.
- Filters wills via case assigned_lawyer with active case statuses + (POST_DEATH_VERIFY OR PRE_DEATH_REVIEW with active disclosure).
- Read-only serializer (`title`, `content`, `status`, `version`, `finalized_at`).

### 2.3 WILL DISCLOSURE / EVIDENCE ACCESS — VERIFIED ✅
- Disclosure download requires: assigned lawyer + `lawyer_case_scope_is_authorized` + `is_active` disclosure.
- Evidence download: initiator | assigned lawyer | administrator; lawyer requires scope; downloads use private storage with no-store/nosniff headers; audit events emitted.

### 2.4 BENEFICIARY DATA ISOLATION — VERIFIED ✅
- Owner-scoped will/beneficiary/allocation endpoints (`CanManageOwnWills`, `IsOwner`).
- Beneficiary self endpoints scoped by `beneficiary__beneficiary_user=request.user` + normalized email match.
- Release token flows: token hash comparison, expiry check, case APPROVED, allocation VERIFIED + reviewed by assigned lawyer.
- Anti-enumeration preserved (generic 400s, masked emails, 404 for self-allocation denial).

### 2.5 RELEASE / NOTIFICATION SECURITY — VERIFIED ✅
- `BeneficiaryRelease`: `access_token_hash` (SHA-256) + `token_expires_at` (30d) + `first_accessed_at`; HMAC compare.
- `BeneficiaryNotificationOutbox`: status machine, idempotency key, retries with backoff.
- Failed notifications revoke access token (hash cleared, expiry cleared).

### 2.6 AUDIT LOGGING — VERIFIED ✅
- 24 event types + SECURITY_ALERT; actor/target_user/ip/user_agent/details.
- `MyActivityListAPIView`: scoped to actor-or-target, excludes `details`, limit 10.
- Existing regression tests passing.

### 2.7 DATABASE / MIGRATIONS — VERIFIED ✅
- Migrations created via Django (0002 BeneficiaryAllocation, 0002 BeneficiaryRelease_Outbox, 0005/0006 AuditEvent, 0006 User.google_sub).
- Unique constraints on active-case-per-will, beneficiary email/user per will, pending invitation per relationship.

### 2.8 FRONTEND SECURITY — VERIFIED ✅
- Access token held in memory only (not localStorage).
- Refresh via HttpOnly cookie + CSRF header from cookie.
- 401 auto-refresh retry (excluding auth endpoints).
- Google credential handled via GSI custom event → backend verifies.

---

## 3. FINDINGS & REMEDIATION THIS SESSION

### 3.1 FIXED — Temporary Debug Credential Leak (`backend/apps/accounts/services.py`)
**Severity:** Medium → fixed immediately.
- `verify_google_id_token()` contained temporary `print()` statements that logged:
  - token length
  - token prefix (first 10 chars)
  - client_id presence
  - exception reprs
- **Risk:** Google ID tokens are bearer credentials; logging partial token material + lengths is a credential-handling defect.
- **Remediation:** Removed all temporary `print()` statements; retained structured `logger.warning(...)` error logging only.

### 3.2 Observations (not blockers, flagged for final report)
- `UserSerializer` exposes `google_sub`, `account_status`, `email_verified` (read-only fields). Behavior consistent; may be tightened in final report.
- Some invitation audit writes use direct `AuditEvent.objects.create` rather than shared helper; actor values are passed correctly.

---

## 4. TESTS RUN (Final state)

| Suite | Result |
|---|---|
| `backend manage.py check` | **0 issues** ✅ |
| `apps/accounts/tests.py` | **37 passed** ✅ (after debug-print fix) |
| `apps/verification/tests.py` | **70 passed** ✅ |
| `apps/beneficiaries/tests.py` | **36 passed** ✅ |
| `apps/wills/tests.py + apps/audit/tests.py + apps/documents/tests.py` | **62 passed** ✅ |
| Combined core (accounts + wills + audit + documents) | **99 passed** ✅ |
| Full backend suite | ~205 tests collected/passing (accounts/verification/beneficiaries/wills/audit/documents green) |

---

## 5. Conclusion / Next Steps

- Independent audit was in progress.
- Code review findings resolved during session: debug print credential leak removed and retested green.
- Remaining: finalize audit report write-up for supervisor, full-suite final confirmation, and hand-off.

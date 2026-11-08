# WillChain SL — Supervisor Workflow Revision Architecture (Corrected)

**Project:** Design and Development of an AI and Blockchain-Based Digital Will Management System for Secure Storage, Verification, and Beneficiary Access in Sierra Leone.

**Scope:** Module 5 revision (architecture/documentation only). No production code is written during this phase. Module 6 (Blockchain Integrity and Verification) must not begin until this plan is reviewed, approved, and the revised workflow is implemented and tested.

**Status:** Awaiting supervisor review. Approved policy questions pending resolution are marked with `[POLICY QUESTION]`. Legal questions requiring qualified Sierra Leone counsel are marked with `[LEGAL QUESTION]`.

---

## 1. Current Architecture Assessment (Confirmed Existing Implementation)

### 1.1 Technology Stack
- **Backend:** Django 5.2 + Django REST Framework, PostgreSQL, `rest_framework_simplejwt` (JWT), `corsheaders`.
- **Frontend:** Next.js (App Router), TypeScript, JWT access token in memory, refresh token in HttpOnly cookie.
- **Audit:** `apps.audit.AuditEvent` model records `actor`, `target_user`, `ip_address`, `user_agent`, `details` (JSON), `created_at`.
- **Storage:** Private document storage (`private_document_storage`), files under `PRIVATE_DOCUMENT_ROOT`, never served by `/media/`.

### 1.2 Existing Domain Modules
| Module | Responsibility |
|--------|----------------|
| `accounts` | User identity, roles (`OWNER`, `MEMBER`, `WITNESS`, `BENEFICIARY`, `LAWYER_VERIFIER`, `ADMINISTRATOR`), account status (`PENDING_VERIFICATION`, `ACTIVE`, `INACTIVE`, `SUSPENDED`), JWT login/refresh/logout, password reset, email verification, invitations. |
| `wills` | Will drafts/versions/finalisation; owner-only read/write; `WILL_ACCESSED`, `WILL_UPDATED`, `WILL_FINALIZED`, `WILL_DELETED`, `WILL_ACCESS_DENIED` audit events. Finalized/archived wills are read-only. |
| `beneficiaries` | Will-beneficiary relationships (`WillBeneficiary`) + invitations (`BeneficiaryInvitation`); **currently sends email on create/resend** (violates Requirement D). |
| `documents` | Private will documents, integrity checks, versioning; owner-only content access. |
| `verification` | Pre-death review (`PRE_DEATH_REVIEW`) / post-death verification (`POST_DEATH_VERIFY`) cases, evidence, lawyer assignment, decisions, will disclosure authorization/download (pre-death only, owner-gated). |
| `audit` | Security/business-event audit records; `DashboardActivitySerializer` exposes only `id`/`event_type`/`event_label`/`created_at`; `details` never serialized to users. |
| `notifications`, `integrity`, `ai_services` | Directory stubs only; no implementation. |

### 1.3 Security Controls Already In Place
- All endpoints require `IsAuthenticated` + `IsActiveAccount` (`account_status == ACTIVE` AND `email_verified`).
- Lawyer write actions (`begin_review`, `request_information`, `record_decision`, `assess_eligibility`, `set_evidence_sufficiency`) require `assigned_lawyer == actor`.
- Will disclosure download requires assigned lawyer + active `WillDisclosureAuthorization` (pre-death only).
- Audit events capture IP address + user agent from request; will contents/private document contents/storage keys are **never** stored in audit `details`.
- `linked_prior_case` IDOR remediated: `validate_linked_prior_case` enforces `prior.initiator_id == actor.pk` with generic 400.
- Finalized/archived wills are read-only to owner; lawyer has no write endpoints on wills.
- `IsOwner` object permission enforces ownership via `owner`/`user`/`inviter`/`created_by`/`will__owner`.

---

## 2. New Workflow and Affected Modules

### 2.1 Summary of Supervisor Requirements Mapped to Modules
| ID | Requirement | Affected Module(s) | Policy/Legal Question? |
|----|-------------|-------------------|------------------------|
| A | Google OAuth 2.0 / OIDC login + account linking | `accounts` (+ frontend auth) | No (implementation choice: library) |
| B | Lawyer read-only will access during verification | `wills`, `verification`, `audit` | **[POLICY QUESTION B1, B2]** |
| C | Lawyer access audit trail | `audit` (+ all touched views/services) | **[POLICY QUESTION C]** |
| D | No notifications when owner adds/edits beneficiary | `beneficiaries` (+ `notifications`) | No |
| E | Beneficiary-release notification after verification | `verification`, `beneficiaries`, `notifications` | **[POLICY QUESTION E1–E4]** |
| F | Individual beneficiary allocation view | `beneficiaries`, `wills` (+ data model) | **[LEGAL QUESTION F1–F3]** |

### 2.2 High-Level Revised Workflow
1. **Authentication (A).** User signs in via existing email/password **OR** new Google OAuth flow. Both issue the same JWT access token + refresh cookie. Existing roles and account statuses are preserved; Google login never grants privileged roles automatically. Suspended/inactive users blocked at authentication.
2. **Beneficiary Setup — No Early Notification (D).** Owner adds a beneficiary to a DRAFT will — **no email/SMS/push/invitation is sent**. Relationship stored as `PENDING`/`ACTIVE`. Owner may edit/revoke — again, no notification.
3. **Verification Case (Existing).** Case created (pre-death or post-death), evidence uploaded, lawyer assigned by admin.
4. **Lawyer Read-Only Access (B).** Assigned lawyer may view the will content and supporting documents **only** for wills tied to an authorized verification case. Lawyer may never edit/delete/replace/finalize/revoke the will. **[B1, B2 scope pending]**
5. **Lawyer Audit Trail (C).** Every lawyer read action on a will/document and every verification workflow action is recorded in `AuditEvent` (actor, action, will_id, case_id, ip, user_agent, outcome). Denied attempts logged.
6. **Verification Decision (Existing + E).** Lawyer records APPROVED/REJECTED. When release conditions are satisfied, a beneficiary-release operation is **explicitly authorized** (not automatic on APPROVED). **[E1–E4 pending]**
7. **Beneficiary Release Notification (E).** Each eligible beneficiary is notified individually that information is ready for secure access. No will/asset/share details in the message. Secure app link; existing users sign in, new users register and verify email. **Notification does not itself grant access**; backend authorizes allocation view independently via release token.
8. **Beneficiary Allocation View (F).** Beneficiary sees only their own allocated assets/share, asset descriptions, and release status — never the full will or another beneficiary's allocation.

---

## 3. Database Changes — Corrected Data Models

### 3.1 `accounts` — Google Identity Linking (A)
**Minimal, additive changes only.** No existing columns altered.

**Option A (Recommended for simplicity — single field on User):**
```python
# apps/accounts/models.py
class User(AbstractBaseUser, PermissionsMixin):
    ...
    google_sub = models.CharField(max_length=255, unique=True, null=True, blank=True, db_index=True)
    # account_status already has: PENDING_VERIFICATION, ACTIVE, INACTIVE, SUSPENDED
```

**Option B (Extensible — separate table for multiple providers):**
```python
# apps/accounts/models.py (new model)
class SocialAccount(models.Model):
    class Provider(models.TextChoices):
        GOOGLE = 'google', 'Google'
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='social_accounts')
    provider = models.CharField(max_length=32, choices=Provider.choices)
    provider_user_id = models.CharField(max_length=255, db_index=True)  # Google 'sub'
    email = models.EmailField()
    email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['provider', 'provider_user_id'], name='unique_provider_user')]
```
**Decision:** Option A is sufficient for Google-only requirement. Option B adds migration complexity without immediate need. **Recommend Option A**; can refactor to Option B later if more providers added.

### 3.2 `beneficiaries` — Allocation Data Model (F) — **Corrected**
The current `WillBeneficiary` model stores `relationship_type` and `status`, but no per-beneficiary allocation. To support **individual beneficiary allocations** with proper constraints and auditability:

```python
# apps/beneficiaries/models.py (new model)
class BeneficiaryAllocation(models.Model):
    class AllocationType(models.TextChoices):
        FIXED_AMOUNT = 'FIXED_AMOUNT', 'Fixed amount'
        PERCENTAGE = 'PERCENTAGE', 'Percentage of residuary estate'
        SPECIFIC_ITEM = 'SPECIFIC_ITEM', 'Specific item/asset'

    class ReleaseStatus(models.TextChoices):
        PENDING_RELEASE = 'PENDING_RELEASE', 'Pending release'
        RELEASED = 'RELEASED', 'Released to beneficiary'
        WITHHELD = 'WITHHELD', 'Withheld by verifier/admin'

    will = models.ForeignKey('wills.Will', on_delete=models.CASCADE, related_name='allocations')
    beneficiary = models.ForeignKey('WillBeneficiary', on_delete=models.CASCADE, related_name='allocations')
    allocation_type = models.CharField(max_length=32, choices=AllocationType.choices)
    description = models.CharField(max_length=500)  # e.g. "Family home at 123 Main St", "Cash residuary 50%"
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # 0.00–100.00
    amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)  # Sierra Leone Leones (SLL)
    currency = models.CharField(max_length=3, default='SLL')
    release_status = models.CharField(max_length=32, choices=ReleaseStatus.choices, default=ReleaseStatus.PENDING_RELEASE)
    release_authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='authorized_releases'
    )
    release_authorized_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # Percentage must be provided for PERCENTAGE type
            models.CheckConstraint(
                check=(
                    (models.Q(allocation_type='PERCENTAGE') & models.Q(percentage__isnull=False) & models.Q(percentage__gte=0) & models.Q(percentage__lte=100))
                    | ~models.Q(allocation_type='PERCENTAGE')
                ),
                name='allocation_percentage_required'
            ),
            # Amount must be provided for FIXED_AMOUNT type
            models.CheckConstraint(
                check=(
                    (models.Q(allocation_type='FIXED_AMOUNT') & models.Q(amount__isnull=False) & models.Q(amount__gte=0))
                    | ~models.Q(allocation_type='FIXED_AMOUNT')
                ),
                name='allocation_amount_required'
            ),
            # Specific item requires description
            models.CheckConstraint(
                check=(
                    (models.Q(allocation_type='SPECIFIC_ITEM') & ~models.Q(description=''))
                    | ~models.Q(allocation_type='SPECIFIC_ITEM')
                ),
                name='allocation_specific_item_description'
            ),
            # Mutual exclusivity of percentage/amount per type (enforced above)
        ]
        indexes = [
            models.Index(fields=['will', 'beneficiary']),
            models.Index(fields=['release_status']),
        ]
```

**Key Corrections from Prior Draft:**
- **Relationship consistency:** Allocation FK to `WillBeneficiary` (not directly to `User`) ensures allocation belongs to a specific will-beneficiary relationship.
- **Valid constraints:** CheckConstraints enforce percentage/amount presence per type; percentage bounded 0–100; amount non-negative.
- **Currency:** Explicit `currency` field (default `SLL`); do not assume USD.
- **Specific items:** Description required for `SPECIFIC_ITEM`; supports "Family home", "Vehicle registration X123", etc.
- **Multiple allocations per beneficiary:** One `WillBeneficiary` can have many `BeneficiaryAllocation` rows (e.g., specific house + percentage of residue).
- **Contingent/withheld allocations:** `release_status = WITHHELD` supports verifier/admin holding back an allocation (e.g., pending debt resolution). `PENDING_RELEASE` is the initial state.
- **Cross-access prevention:** Queries **always** filter by `beneficiary__beneficiary_user == request.user`. No allocation endpoint accepts a will_id without relationship ownership check.
- **No Sierra Leone inheritance rules invented:** Model is flexible; actual allocation structure (percentages, fixed amounts, specific items) is data, not code logic.

### 3.3 `verification` — Beneficiary Release Tracking (E) — **Corrected**
**A single Boolean on `VerificationCase` is INSUFFICIENT.** It cannot represent:
- Partial release (some beneficiaries released, others withheld)
- Multiple releases per case (e.g., phased release)
- Which specific allocations were released
- Audit trail per beneficiary
- Notification retry state

**Recommended: Dedicated `BeneficiaryRelease` model (one row per beneficiary per case):**

```python
# apps/verification/models.py (new model)
class BeneficiaryRelease(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Release pending authorization'
        AUTHORIZED = 'AUTHORIZED', 'Release authorized, notification queued'
        NOTIFIED = 'NOTIFIED', 'Notification sent'
        ACKNOWLEDGED = 'ACKNOWLEDGED', 'Beneficiary has accessed allocation'
        FAILED = 'FAILED', 'Notification failed (retry eligible)'

    verification_case = models.ForeignKey('VerificationCase', on_delete=models.CASCADE, related_name='beneficiary_releases')
    beneficiary = models.ForeignKey('beneficiaries.WillBeneficiary', on_delete=models.CASCADE, related_name='releases')
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING, db_index=True)
    
    # Release authorization (who, when)
    authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='authorized_beneficiary_releases'
    )
    authorized_at = models.DateTimeField(null=True, blank=True)
    
    # Notification tracking
    notification_sent_at = models.DateTimeField(null=True, blank=True)
    notification_channel = models.CharField(max_length=32, blank=True)  # 'email', 'sms'
    notification_retry_count = models.PositiveSmallIntegerField(default=0)
    notification_last_error = models.TextField(blank=True)
    
    # Beneficiary access token (hashed, single-use)
    access_token_hash = models.CharField(max_length=64, unique=True, null=True, blank=True, db_index=True)
    access_token_created_at = models.DateTimeField(null=True, blank=True)
    first_accessed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['verification_case', 'beneficiary'], name='unique_release_per_case_beneficiary'),
        ]
        indexes = [
            models.Index(fields=['verification_case', 'status']),
            models.Index(fields=['beneficiary', 'status']),
        ]
```

**Why this design:**
- **Partial release:** Each beneficiary has independent status.
- **Withheld allocations:** `BeneficiaryAllocation.release_status = WITHHELD` + `BeneficiaryRelease.status = PENDING` (or no release row).
- **Duplicate prevention:** Unique constraint on `(verification_case, beneficiary)`.
- **Notification retries:** `notification_retry_count`, `notification_last_error` support outbox pattern (§7).
- **Transaction safety:** Release authorization + `BeneficiaryRelease` row creation in single atomic transaction.
- **Audit logging:** Each state change emits `AuditEvent` (see §7).
- **Multiple beneficiaries:** One row each; queried by `verification_case.beneficiary_releases.all()`.
- **Multiple verification cases:** Each case has its own releases; a will can have multiple verification cases over time (e.g., rejected then new case).
- **Will amendments:** If will is amended (new version, new finalization), a **new** verification case is created. Old releases remain attached to old case for audit. New case gets new release rows.

**On `VerificationCase` — add only:**
```python
# apps/verification/models.py (add to existing VerificationCase)
release_authorized_by = models.ForeignKey(
    settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
    related_name='authorized_verification_releases'
)
release_authorized_at = models.DateTimeField(null=True, blank=True)
# Note: per-beneficiary detail lives in BeneficiaryRelease
```

### 3.4 `audit` — Lawyer Access Event Types (C)
Add new `EventType` choices to `AuditEvent.EventType` (existing model):

```
LAWYER_WILL_VIEWED = 'LAWYER_WILL_VIEWED', 'Lawyer viewed will'
LAWYER_WILL_DOWNLOADED = 'LAWYER_WILL_DOWNLOADED', 'Lawyer downloaded will copy'
LAWYER_DOCUMENT_VIEWED = 'LAWYER_DOCUMENT_VIEWED', 'Lawyer viewed supporting document'
LAWYER_REVIEW_STARTED = 'LAWYER_REVIEW_STARTED', 'Lawyer started review'  # reuse/extend VERIFICATION_REVIEW_BEGUN
LAWYER_INFORMATION_REQUESTED = 'LAWYER_INFORMATION_REQUESTED', 'Lawyer requested information'
LAWYER_DECISION_RECORDED = 'LAWYER_DECISION_RECORDED', 'Lawyer recorded decision'
LAWYER_UNAUTHORIZED_WILL_EDIT_ATTEMPT = 'LAWYER_UNAUTHORIZED_WILL_EDIT_ATTEMPT', 'Unauthorized will edit attempt'
LAWYER_UNAUTHORIZED_DOCUMENT_ACCESS_ATTEMPT = 'LAWYER_UNAUTHORIZED_DOCUMENT_ACCESS_ATTEMPT', 'Unauthorized document access attempt'

BENEFICIARY_RELEASE_AUTHORIZED = 'BENEFICIARY_RELEASE_AUTHORIZED', 'Beneficiary release authorized'
BENEFICIARY_RELEASE_NOTIFIED = 'BENEFICIARY_RELEASE_NOTIFIED', 'Beneficiary release notification sent'
BENEFICIARY_ALLOCATION_ACCESSED = 'BENEFICIARY_ALLOCATION_ACCESSED', 'Beneficiary accessed own allocation'
BENEFICIARY_ALLOCATION_ACCESS_DENIED = 'BENEFICIARY_ALLOCATION_ACCESS_DENIED', 'Beneficiary allocation access denied'
```

**Append-only protection (Deployment Hardening — [POLICY QUESTION C]):**
`AuditEvent` has no code-level protection against deletion by DB-owning admins. Recommend PostgreSQL-level:
```sql
REVOKE DELETE ON audit_auditevent FROM willchain_app_role;
-- Only superuser/backup role can delete; application role can INSERT/SELECT only
```
State as deployment item, not code.

---

## 4. API Endpoint Changes — Revised Design

### 4.1 `accounts` — Google Authentication (A)
| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/v1/auth/google/login/` | POST | `AllowAny` | Accept Google ID token; validate issuer/audience/expiry/signature; link or create account; issue JWT + refresh cookie. |
| `/api/v1/auth/google/link/` | POST | `IsAuthenticated` + `IsActiveAccount` | Link an existing **verified** account to a Google account (validate Google ID token, bind `google_sub`). |
| `/api/v1/auth/google/unlink/` | POST | `IsAuthenticated` + `IsActiveAccount` | Remove Google linkage; user falls back to password. |

**Behavior Clarifications (per correction prompt):**

| Scenario | Flow | Security Controls |
|----------|------|-------------------|
| **Existing user signs in with Google** | POST `/google/login/` with ID token → backend validates token → finds `User` by `google_sub` → if `account_status=ACTIVE` and `email_verified` → issue JWT. | Suspended/inactive blocked. No role escalation. |
| **Existing user links Google to authenticated account** | 1. User signs in with password (existing flow).<br>2. Frontend gets Google ID token via Google SDK.<br>3. POST `/google/link/` with ID token.<br>4. Backend validates token, checks `email` + `email_verified=true` matches `request.user.email`.<br>5. Sets `user.google_sub = token.sub`. | Prevents takeover: requires password auth + email match. No auto-link on email alone. |
| **New beneficiary registers after authorized release** | 1. Beneficiary clicks release link (contains single-use access token).<br>2. Frontend validates token via `/api/v1/beneficiary-release/validate-token/`.<br>3. If valid, shows registration form pre-filled with masked email.<br>4. POST `/auth/register/` with email, name, password.<br>5. Backend creates `User` with `role=BENEFICIARY`, `account_status=PENDING_VERIFICATION`, `email_verified=false` (local verification still required).<br>6. Email verification sent (existing flow).<br>7. After verification → account ACTIVE → can access allocation. | **Email knowledge alone is NOT sufficient.** Release token proves entitlement. New account still requires local email verification. Google login for new beneficiary follows same flow as any new user. |
| **Pending accounts** | `PENDING_VERIFICATION` users cannot obtain JWT (login fails in `LoginSerializer.validate`). Google login creates account with `PENDING_VERIFICATION`; email verification required before activation. | Protected resources require `IsActiveAccount` → blocked. |

**Token Validation Implementation:**
- **Do NOT** assume Google client secret needed for frontend. Frontend uses Google Identity Services (GIS) SDK with **public** `GOOGLE_OAUTH2_CLIENT_ID` to obtain ID token. Client secret used **only** by backend if using authorization code flow (not needed for ID token flow).
- **Backend validates ID token server-side only.** Use a maintained library: **`google-auth`** (official Google library, lightweight, no Django coupling) for ID token verification:
  ```python
  from google.oauth2 import id_token
  from google.auth.transport import requests as google_requests
  
  def verify_google_id_token(id_token_str: str, client_id: str) -> dict:
      return id_token.verify_oauth2_token(
          id_token_str,
          google_requests.Request(),
          client_id,
          clock_skew_in_seconds=10
      )
  ```
  This validates issuer, audience, expiry, signature via Google's JWKS (cached by library). **Do not implement manual JWKS fetching.**
- Rate-limit `/auth/google/login/` under existing `auth` throttle scope.
- `GOOGLE_OAUTH2_CLIENT_ID` (public) may be exposed to frontend for GIS SDK. `GOOGLE_OAUTH2_CLIENT_SECRET` is **backend env var only**; never in frontend code.
- Preserve JWT session handling (15-min access, 7-day refresh, rotation, blacklisting).

### 4.2 `wills` — Lawyer Read-Only Access (B)
**New endpoint(s):**

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/v1/wills/<pk>/lawyer-view/` | GET | `IsAuthenticated` + `IsActiveAccount` + `IsAssignedLawyerOnAuthorizedCase` | Return will metadata + content (title, content JSON, status, version, finalized_at) for lawyer to read. **No mutation.** |
| `/api/v1/wills/<pk>/lawyer-documents/` | GET | Same as above | List supporting documents metadata (no file download unless `[B2]` approved). |

**Authorization Rule (B) — Enforced at All Layers:**

1. **API Layer (Permission Class):**
   ```python
   # apps/verification/permissions.py (new)
   class IsAssignedLawyerOnAuthorizedCase(BasePermission):
       """
       Grants access iff:
       - request.user.role == LAWYER_VERIFIER
       - request.user.account_status == ACTIVE
       - Exists VerificationCase where:
           - case.assigned_lawyer == request.user
           - case.will_id == will.pk
           - case.status in AUTHORIZED_STATUSES (defined by [B1])
       """
       def has_permission(self, request, view):
           will_pk = view.kwargs['pk']
           return VerificationCase.objects.filter(
               assigned_lawyer=request.user,
               will_id=will_pk,
               status__in=AUTHORIZED_STATUSES  # [B1] defines this
           ).exists()
   ```

2. **Queryset Layer (View):**
   ```python
   # apps/wills/views.py (new view)
   class LawyerWillViewAPIView(generics.RetrieveAPIView):
       permission_classes = [IsAuthenticated, IsActiveAccount, IsAssignedLawyerOnAuthorizedCase]
       serializer_class = LawyerWillReadOnlySerializer
       
       def get_queryset(self):
           # Returns 404 if no authorized case exists (anti-enumeration)
           return Will.objects.filter(
               pk=self.kwargs['pk'],
               verification_cases__assigned_lawyer=self.request.user,
               verification_cases__status__in=AUTHORIZED_STATUSES
           ).distinct()
   ```

3. **Service Layer (No mutation methods exposed):**
   - No `update`, `delete`, `finalize` endpoints for lawyer.
   - `Will.is_read_only` property already prevents owner edits on finalized; lawyer has no path to call owner endpoints.

**Anti-Enumeration:** Returns **404** (not 403) when no authorized case exists — consistent with existing `WillDetailAPIView.get_object`.

**Documents:** Lawyer may view supporting document metadata via `/lawyer-documents/`. File download **only if `[B2]` approved** (see §6). If approved, reuse `WillDocumentDownloadAPIView` with extended permission check.

**Scope Policy Question [B1] (Must be resolved before implementation):**
- **Option 1 (Pre-death only):** Lawyer reads will via existing `WillDisclosureAuthorization` (owner-gated). No new endpoint needed; reuse `WillDisclosureDownloadAPIView`.
- **Option 2 (Post-death only):** Lawyer reads finalized will + documents during `POST_DEATH_VERIFY` case in `UNDER_REVIEW`/`APPROVED`. New endpoint required.
- **Option 3 (Both):** Both Option 1 and Option 2.

**Document Download Policy Question [B2]:** May lawyer download supporting documents (not just metadata)? If yes, under what authorization (assigned lawyer + active case + document tied to case will)?

### 4.3 `beneficiaries` — Allocation View (F)
| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/v1/me/beneficiary-allocations/` | GET | `IsAuthenticated` + `IsActiveAccount` + `role=BENEFICIARY` | List own allocations across wills (summary: will title, allocation type, description, release_status). |
| `/api/v1/me/beneficiary-allocations/<allocation_pk>/` | GET | Same + ownership check | Detail view for one allocation (asset description, amount/percentage, release status). |
| `/api/v1/beneficiary-release/validate-token/` | POST | `AllowAny` | Validate single-use release access token (from notification link); returns `{valid: true, beneficiary_email_masked, will_title}` for registration UI. |
| `/api/v1/beneficiary-release/claim/` | POST | `AllowAny` | Accept release token + registration data (or login) → bind user to `WillBeneficiary` → issue JWT → redirect to allocation view. |

**Query Scoping (Cross-Access Prevention):**
```python
# apps/beneficiaries/views.py
class MyAllocationsListAPIView(generics.ListAPIView):
    serializer_class = BeneficiaryAllocationSummarySerializer
    permission_classes = [IsAuthenticated, IsActiveAccount]
    
    def get_queryset(self):
        return BeneficiaryAllocation.objects.filter(
            beneficiary__beneficiary_user=self.request.user,
            beneficiary__status=WillBeneficiary.Status.ACTIVE
        ).select_related('will', 'beneficiary')
```

### 4.4 `verification` — Release Authorization & Notification (E)
| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/v1/verification/cases/<pk>/authorize-release/` | POST | `IsAuthenticated` + `IsActiveAccount` + `IsAdministrator` **OR** `IsAssignedLawyer` (with `[E1]` policy) | Explicitly authorize beneficiary release for an APPROVED case. Creates `BeneficiaryRelease` rows for eligible beneficiaries. Queues notifications. |
| `/api/v1/verification/cases/<pk>/release-status/` | GET | `IsAuthenticated` + `IsActiveAccount` + case access | Returns release status per beneficiary (PENDING/AUTHORIZED/NOTIFIED/ACKNOWLEDGED/FAILED). |

---

## 5. Authentication Architecture — Detailed (A)

### 5.1 Google ID Token Flow (Frontend → Backend)
```
1. Frontend: Google Identity Services (GIS) SDK → user clicks "Sign in with Google"
2. GIS returns ID token (JWT) to frontend (client-side only)
3. Frontend POSTs {id_token} to /api/v1/auth/google/login/
4. Backend:
   a. verify_google_id_token(id_token, GOOGLE_OAUTH2_CLIENT_ID) → payload
   b. payload must have: email_verified=true, exp>now, aud=client_id, iss∈{accounts.google.com, https://accounts.google.com}
   c. Extract: sub (google_sub), email, given_name, family_name
   d. Lookup User by google_sub:
      - Found + ACTIVE + email_verified → issue JWT, update last_login
      - Found + SUSPENDED/INACTIVE → 403 ACCOUNT_INACTIVE
   e. If not found by google_sub, lookup by email (case-insensitive):
      - Found + email_verified (local) → offer LINK flow (return 409 LINK_REQUIRED with link_token)
      - Not found → create User(role=BENEFICIARY, account_status=PENDING_VERIFICATION, email_verified=False, unusable_password, google_sub=sub) → issue JWT
5. Response: {access, user} + refresh cookie
```

### 5.2 Account Linking Flow (Existing User + Google)
```
Prereq: User has authenticated via password (has valid JWT)
1. Frontend obtains Google ID token via GIS SDK (popup)
2. POST /api/v1/auth/google/link/ {id_token}
3. Backend:
   a. verify_google_id_token(...)
   b. Require: token.email.lower() == request.user.email.lower() AND token.email_verified == True
   c. Require: request.user.google_sub is None (not already linked)
   d. Set request.user.google_sub = token.sub; save()
   e. Audit: LAWYER_GOOGLE_LINKED (or USER_GOOGLE_LINKED)
4. Response: 200 OK
```
**Takeover Prevention:** Linking requires **both** password authentication (proves ownership of local account) **and** Google email match with `email_verified=true`. No auto-linking on email alone.

### 5.3 Pending Account Protection
- `PENDING_VERIFICATION` users: `LoginSerializer.validate` rejects if `account_status != ACTIVE` or `not email_verified`.
- Google login creates `PENDING_VERIFICATION` account; email verification email sent (existing flow).
- `IsActiveAccount` permission blocks all protected endpoints until `ACTIVE` + `email_verified`.
- Lawyer/beneficiary/allocations endpoints all require `IsActiveAccount` → pending users cannot access.

---

## 6. Lawyer Read-Only Access — Enforcement Verification (B)

### 6.1 Exact Eligible Verification-Case States
**[POLICY QUESTION B1 — Must be answered]**

| Option | Case Types | Case Statuses | Notes |
|--------|------------|---------------|-------|
| **1. Pre-death only** | `PRE_DEATH_REVIEW` | `OPEN`, `UNDER_REVIEW`, `APPROVED` | Uses existing `WillDisclosureAuthorization` gate. No new endpoint. |
| **2. Post-death only** | `POST_DEATH_VERIFY` | `UNDER_REVIEW`, `APPROVED` | New endpoint required. Removes owner-disclosure safeguard. |
| **3. Both** | Both | As above | Two separate access paths. |

**Recommendation:** Present Options 1, 2, 3 to supervisor. Do not implement until approved.

### 6.2 Permission Enforcement at All Layers

| Layer | Mechanism | Verification |
|-------|-----------|--------------|
| **API (Permission)** | `IsAssignedLawyerOnAuthorizedCase` | Checks `VerificationCase` existence with `assigned_lawyer=request.user`, `will_id=pk`, `status∈AUTHORIZED_STATUSES` |
| **Queryset (View)** | `get_queryset()` filters by `verification_cases__assigned_lawyer=request.user` | Returns 404 if no match (anti-enumeration) |
| **Service** | No mutation methods on lawyer view; `Will.is_read_only` prevents owner edits on finalized | Lawyer cannot call owner endpoints (different URL namespace) |
| **Object (Serializer)** | `LawyerWillReadOnlySerializer` — all fields `read_only=True` | No write fields exposed |

### 6.3 Endpoint Inspection for Bypass Prevention

| Endpoint | Current Auth | Lawyer Access? | Mitigation |
|----------|--------------|----------------|------------|
| `GET /wills/<pk>/` | Owner only (`IsOwner`) | No | Lawyer not owner → 404 |
| `PATCH /wills/<pk>/` | Owner only | No | 404 |
| `DELETE /wills/<pk>/` | Owner only | No | 404 |
| `POST /wills/<pk>/finalize/` | Owner only | No | 404 |
| `GET /wills/<pk>/documents/` | Owner only | No | 404 |
| `GET /wills/<pk>/documents/<doc_pk>/download/` | Owner only | **Only if [B2] approved** | New permission check |
| `GET /verification/cases/<pk>/` | Initiator/Lawyer/Admin | Yes (case detail) | Existing `CanViewCase` |
| `GET /verification/cases/<pk>/evidence/` | Initiator/Lawyer/Admin | Yes (evidence list) | Existing |
| `GET /verification/cases/<pk>/evidence/<ev_pk>/download/` | Initiator/Lawyer/Admin | Yes (evidence file) | Existing |
| `POST /verification/cases/<pk>/begin-review/` | Assigned lawyer | Yes | Existing |
| `POST /verification/cases/<pk>/decision/` | Assigned lawyer | Yes | Existing |
| **NEW `GET /wills/<pk>/lawyer-view/`** | **Assigned lawyer + authorized case** | **Yes (read-only)** | **New permission** |
| **NEW `GET /wills/<pk>/lawyer-documents/`** | **Assigned lawyer + authorized case** | **Yes (metadata)** | **New permission** |

**Confirmed:** No path for lawyer to mutate will content, documents, beneficiary relationships, or allocations.

---

## 7. Beneficiary Allocation Model — Detailed Review (F)

### 7.1 Relationship Consistency
```
Will (1) ──────< BeneficiaryAllocation (N)
    │
    └─< WillBeneficiary (N) ──< BeneficiaryAllocation (N)
                              ↑
                         beneficiary FK
```
- Allocation belongs to **one Will** and **one WillBeneficiary** (relationship).
- `WillBeneficiary` links to `User` via `beneficiary_user` (nullable until invitation accepted).
- Queries for beneficiary: `BeneficiaryAllocation.objects.filter(beneficiary__beneficiary_user=request.user)`.

### 7.2 Constraints Summary
| Allocation Type | Required Fields | Constraints |
|-----------------|-----------------|-------------|
| `PERCENTAGE` | `percentage` (0.00–100.00) | `CheckConstraint` enforces presence + bounds |
| `FIXED_AMOUNT` | `amount` (≥ 0) | `CheckConstraint` enforces presence + non-negative |
| `SPECIFIC_ITEM` | `description` (non-empty) | `CheckConstraint` enforces non-empty |

### 7.3 Currency
- `currency` field (ISO 4217, default `SLL`).
- Amounts stored in **minor units** (leones, not cents) or as `Decimal` with 2 decimal places. Use `DecimalField(max_digits=15, decimal_places=2)` for SLL (no subunit).

### 7.4 Multiple Allocations Per Beneficiary
- One `WillBeneficiary` → many `BeneficiaryAllocation`.
- Example: Specific house (`SPECIFIC_ITEM`) + 30% residue (`PERCENTAGE`) + fixed cash gift (`FIXED_AMOUNT`).

### 7.5 Contingent & Withheld Allocations
- `release_status = WITHHELD` — verifier/admin explicitly holds back.
- `release_status = PENDING_RELEASE` — initial state, awaiting release authorization.
- Contingent conditions stored in `description` or future `conditions` JSON field (not in v1).

### 7.6 Cross-Beneficiary / Cross-Will Access Prevention
- **No allocation endpoint accepts `will_id` without ownership check.**
- All queries filter by `beneficiary__beneficiary_user == request.user`.
- Serializer excludes `will.content`, other beneficiaries' allocations, `storage_key`.

---

## 8. Beneficiary Release Architecture — Detailed Design (E)

### 8.1 Why Dedicated `BeneficiaryRelease` Model (Not Boolean)
| Requirement | Boolean on Case | `BeneficiaryRelease` Model |
|-------------|-----------------|----------------------------|
| Partial release (some beneficiaries) | ❌ | ✅ Per-beneficiary row |
| Withheld allocations | ❌ | ✅ `status=PENDING` + `Allocation.release_status=WITHHELD` |
| Duplicate prevention | ❌ | ✅ Unique constraint `(case, beneficiary)` |
| Notification retry tracking | ❌ | ✅ `retry_count`, `last_error` |
| Transaction safety | ❌ | ✅ Atomic release auth + row creation |
| Audit per beneficiary | ❌ | ✅ `AuditEvent` per row state change |
| Multiple beneficiaries | ❌ | ✅ One row each |
| Multiple verification cases | ❌ | ✅ FK to `VerificationCase` |
| Will amendments / subsequent cases | ❌ | ✅ Each case has own releases |

### 8.2 Release State Machine
```
PENDING → AUTHORIZED → NOTIFIED → ACKNOWLEDGED
                │           │
                │           └─ (notification fails) → FAILED → (retry) → NOTIFIED
                └─ (admin cancels) → PENDING
```
- **PENDING:** Created when case APPROVED, but release not yet authorized.
- **AUTHORIZED:** Admin/lawyer (per `[E1]`) explicitly authorizes release → `BeneficiaryRelease` rows created/updated, `authorized_by`/`authorized_at` set.
- **NOTIFIED:** Notification sent (email) → `notification_sent_at`, `notification_channel` set.
- **ACKNOWLEDGED:** Beneficiary accesses allocation via release token → `first_accessed_at` set.
- **FAILED:** Notification delivery failed → `retry_count` incremented, `last_error` stored.

### 8.3 Release Authorization vs Verification Decision
**[POLICY QUESTION E1 — Must be answered]**
- **Verification Decision (Lawyer):** Records APPROVED/REJECTED on case. **Does NOT trigger release.**
- **Release Authorization (Admin or Lawyer per [E1]):** Explicit action on APPROVED case to create `BeneficiaryRelease` rows and queue notifications.
- **Who can authorize?** Options:
  - **Admin only** (safest, current architecture pattern: admin assigns lawyer, admin could authorize release)
  - **Assigned Lawyer** (if `[E1]` approves)
  - **Both** (Admin or assigned lawyer)

**[POLICY QUESTION E2]:** Does `APPROVED` on a `POST_DEATH_VERIFY` case automatically mean **all** beneficiaries' allocations can be released? Or can some be withheld (e.g., minor children, disputed claims)?

**[POLICY QUESTION E3]:** Can a `PRE_DEATH_REVIEW` case trigger beneficiary release? (Current architecture: pre-death is advisory only — **likely No**. Confirm.)

**[POLICY QUESTION E4]:** What if a will has multiple `POST_DEATH_VERIFY` cases (e.g., first rejected, second approved)? Release tied to **specific approved case**; new case gets new `BeneficiaryRelease` rows.

### 8.4 Release Token (Beneficiary Access)
- Generated at `AUTHORIZED` → `NOTIFIED` transition.
- Cryptographically random 32-byte token → SHA-256 hash stored in `access_token_hash`.
- Included in notification link: `https://app.willchain.sl/beneficiary/release/<raw_token>`.
- **Single-use:** On first successful access (`/beneficiary-release/claim/`), `first_accessed_at` set; token can be invalidated (set hash to null) or kept for audit.
- **Short-lived:** Token valid for 30 days (configurable). Expired tokens → `FAILED` or new token generated on re-notify.

### 8.5 Notification Content (Per Requirement E)
- **Contains:** "Information is ready for secure access on WillChain SL. Sign in to view your allocation."
- **Does NOT contain:** Will content, asset details, percentage shares, other beneficiary info, will title (optional, but safer to omit).
- **Link:** Directs to `/beneficiary/release/<token>` (frontend route).

---

## 9. New Beneficiary Account Binding — Secure Process (E)

### 9.1 Flow: No Existing WillChain Account
```
1. Beneficiary clicks release link: /beneficiary/release/<raw_token>
2. Frontend calls POST /api/v1/beneficiary-release/validate-token/ {token: raw_token}
3. Backend:
   a. Hash token → lookup BeneficiaryRelease by access_token_hash
   b. If not found / status not in {AUTHORIZED, NOTIFIED} → 404
   c. Return {valid: true, beneficiary_email_masked: "j***@example.com", will_title: "John's Will"}
4. Frontend shows registration form (pre-fills masked email, user enters full email, name, password)
5. User submits registration → POST /api/v1/auth/register/ {email, first_name, last_name, password, password_confirmation}
6. Backend:
   a. Creates User(role=BENEFICIARY, account_status=PENDING_VERIFICATION, email_verified=False)
   b. Sends email verification (existing flow)
   c. Returns {user, message: "Verify your email to access your allocation"}
7. User verifies email (existing /auth/verify-email/) → account_status=ACTIVE
8. User signs in (existing /auth/login/) → gets JWT
9. Frontend calls POST /api/v1/beneficiary-release/claim/ {token: raw_token}
10. Backend:
    a. Validates token again (hash lookup)
    b. Binds User to WillBeneficiary: release.beneficiary.beneficiary_user = user; release.beneficiary.status = ACTIVE; release.beneficiary.accepted_at = now()
    c. Updates release: status=ACKNOWLEDGED, first_accessed_at=now(), access_token_hash=NULL (invalidate)
    d. Issues JWT + refresh cookie (standard login response)
    e. Audit: BENEFICIARY_ALLOCATION_ACCESSED
11. Frontend redirects to /me/beneficiary-allocations/
```

### 9.2 Security Properties
- **Email knowledge alone is NOT sufficient.** Release token (delivered via email to the beneficiary's address on record) proves entitlement.
- Token is **single-use**, **short-lived**, **securely hashed** at rest (SHA-256).
- New account still requires **local email verification** (not just Google-verified email).
- If beneficiary already has account: step 5–8 skipped; step 9 binds existing authenticated user.

### 9.3 Identity Verification (Beyond Email)
- Current flow: Release token + email verification = sufficient for v1.
- **Future enhancement (not v1):** SMS verification, ID document upload, knowledge-based authentication (KBA) for high-value estates.

---

## 10. Release Authorization — Distinctions (E)

| Operation | Actor | Trigger | Effect | Audit |
|-----------|-------|---------|--------|-------|
| **Lawyer records verification decision** | Assigned Lawyer | POST `/cases/<pk>/decision/` {decision: APPROVED} | `VerificationCase.status = APPROVED` | `LAWYER_DECISION_RECORDED` |
| **Verification completion** | System | Case status = APPROVED + all required steps done | Case is "complete" but **release not authorized** | — |
| **Release authorization** | Admin (or Lawyer per [E1]) | POST `/cases/<pk>/authorize-release/` | Creates `BeneficiaryRelease` rows (PENDING→AUTHORIZED); queues notifications | `BENEFICIARY_RELEASE_AUTHORIZED` (per beneficiary) |
| **Beneficiary notification** | System (async) | Release authorized → notification task | Sends email with release link | `BENEFICIARY_RELEASE_NOTIFIED` |
| **Beneficiary access** | Beneficiary | Clicks link → validates token → registers/logs in → claims | Binds user to relationship; invalidates token; allocation viewable | `BENEFICIARY_ALLOCATION_ACCESSED` |

**Critical:** `APPROVED` **≠** Release Authorized. Release is a **separate, explicit, audited action**. This prevents accidental release when a case is approved but some allocations must be withheld.

---

## 11. Audit and Notification Reliability (C, E)

### 11.1 Audit-Event Completeness
| Action | Event Type | Details Included |
|--------|------------|------------------|
| Lawyer views will | `LAWYER_WILL_VIEWED` | `will_id`, `case_id`, `ip`, `user_agent`, `outcome=success` |
| Lawyer downloads will | `LAWYER_WILL_DOWNLOADED` | `will_id`, `case_id`, `ip`, `user_agent` |
| Lawyer views document | `LAWYER_DOCUMENT_VIEWED` | `document_id`, `will_id`, `case_id` |
| Lawyer starts review | `LAWYER_REVIEW_STARTED` | `case_id` |
| Lawyer requests info | `LAWYER_INFORMATION_REQUESTED` | `case_id`, `notes_length` |
| Lawyer records decision | `LAWYER_DECISION_RECORDED` | `case_id`, `decision` (APPROVED/REJECTED) |
| Lawyer unauthorized edit | `LAWYER_UNAUTHORIZED_WILL_EDIT_ATTEMPT` | `will_id`, `case_id`, `ip`, `outcome=denied` |
| Release authorized | `BENEFICIARY_RELEASE_AUTHORIZED` | `case_id`, `beneficiary_id`, `authorized_by` |
| Notification sent | `BENEFICIARY_RELEASE_NOTIFIED` | `release_id`, `channel`, `recipient_email_masked` |
| Beneficiary accesses | `BENEFICIARY_ALLOCATION_ACCESSED` | `release_id`, `allocation_ids`, `ip` |
| Access denied | `BENEFICIARY_ALLOCATION_ACCESS_DENIED` | `release_id`, `ip`, `reason` |

**Sensitive Data Exclusions (Confirmed):**
- `AuditEvent.details` **never** contains: will content, document contents, storage keys, passwords, tokens, full beneficiary PII (only masked email/reference IDs).

### 11.2 Append-Only Protection
- **Code-level:** No `DELETE`/`UPDATE` endpoints for `AuditEvent`. `AuditEvent` model has no `save()` override allowing mutation.
- **Database-level (Deployment Hardening — [POLICY QUESTION C]):**
  ```sql
  REVOKE DELETE, UPDATE ON audit_auditevent FROM willchain_app_role;
  GRANT INSERT, SELECT ON audit_auditevent TO willchain_app_role;
  -- Only superuser/backup can delete/update
  ```

### 11.3 Denied Access Logging
- All lawyer will/document access attempts (authorized + unauthorized) logged.
- `WillDetailAPIView.get_object` already logs `WILL_ACCESS_DENIED` for IDOR attempts.
- New `LawyerWillViewAPIView` logs `LAWYER_WILL_VIEWED` on success; permission denial returns 404 (anti-enumeration) but **also logs** `LAWYER_UNAUTHORIZED_WILL_EDIT_ATTEMPT` for any write attempt.

### 11.4 Notification Reliability — Transactional Outbox Pattern
**Problem:** Sending email in same transaction as release authorization risks:
- Email sent but transaction rolls back → duplicate notification on retry.
- Transaction commits but email fails → lost notification.

**Solution: Transactional Outbox (v1 — simple implementation; can upgrade to Celery + outbox table later).**

```python
# apps/notifications/models.py (new)
class NotificationOutbox(models.Model):
    class Channel(models.TextChoices):
        EMAIL = 'EMAIL', 'Email'
        SMS = 'SMS', 'SMS'
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SENT = 'SENT', 'Sent'
        FAILED = 'FAILED', 'Failed'
    
    channel = models.CharField(max_length=16, choices=Channel.choices)
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    related_release = models.ForeignKey('verification.BeneficiaryRelease', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
```

**Flow:**
1. `authorize_release` transaction:
   - Creates `BeneficiaryRelease` rows (AUTHORIZED).
   - Creates `NotificationOutbox` rows (PENDING) for each beneficiary.
   - Commits atomically.
2. Background worker (or management command `send_pending_notifications` run via cron/Celery beat):
   - Selects `PENDING` outbox rows (limit 100, ordered by `created_at`).
   - For each: sends email → updates `status=SENT`, `sent_at=now()` **OR** increments `retry_count`, sets `last_error`, `status=FAILED` if max retries exceeded.
   - Idempotent: `NotificationOutbox` row is the source of truth; duplicate sends prevented by status check.
3. `BeneficiaryRelease.notification_sent_at` updated from outbox `sent_at` (or separate task).

**Benefits:** No lost notifications, no duplicates, retryable, auditable.

---

## 12. Updated Test Plan

| Test Area | Cases |
|-----------|-------|
| **Google Auth (A)** | Valid ID token → JWT issued; invalid/expired/wrong aud → 400; account takeover attempt (Google email ≠ local verified email) → 400; link existing account → binding works; suspended user → 403; privileged role never auto-granted; pending account blocked at protected endpoints. |
| **Lawyer Will Read (B)** | Assigned lawyer + authorized case → 200 with will content; unassigned lawyer → 404; lawyer on different case/will → 404; non-lawyer → 404; PUT/PATCH/DELETE by lawyer → 405/403; finalized will not editable by anyone except owner (draft only); document metadata visible; download only if [B2] approved. |
| **Lawyer Audit Trail (C)** | Each lawyer will/document view and verification action produces `AuditEvent` with correct actor, event_type, will_id, case_id, ip, user_agent, outcome. Unauthorized edit attempts recorded as `LAWYER_UNAUTHORIZED_WILL_EDIT_ATTEMPT`. Denied document access → `LAWYER_UNAUTHORIZED_DOCUMENT_ACCESS_ATTEMPT`. |
| **Beneficiary Notification Policy (D)** | Create beneficiary on DRAFT will → **no** email sent; edit relationship → no email; resend (if endpoint remains) → no email; verify `send_beneficiary_invitation_email` is not called. |
| **Beneficiary Release & Notification (E)** | APPROVED case + explicit authorize-release → `BeneficiaryRelease` rows created (PENDING→AUTHORIZED); notification outbox rows created; background worker sends emails; each eligible beneficiary gets one notification with generic message + app link; no will/asset/share details; notification does not grant allocation access until backend authorizes via token claim. Partial release: some beneficiaries AUTHORIZED, others PENDING. Withheld allocations: `Allocation.release_status=WITHHELD`. Duplicate release attempt → 409 (unique constraint). Notification retry on failure → outbox retries. |
| **New Beneficiary Account Binding (E)** | Release token valid → registration form shown; registration creates PENDING_VERIFICATION account; email verification → ACTIVE; claim with token binds user to WillBeneficiary; token invalidated; allocation accessible. Invalid/expired token → 404. Existing user signs in → claim binds existing account. |
| **Allocation View (F)** | Beneficiary sees own allocation/assets/share/release status; cannot see full will or another beneficiary's allocation; unauthenticated → 401; cross-will access prevented (only own relationships). |
| **Release Authorization Distinctions** | Lawyer decision APPROVED ≠ release; explicit authorize-release required; admin (or lawyer per [E1]) can authorize; release creates per-beneficiary rows; audit events at each step. |
| **Audit Reliability** | AuditEvent insert-only (no update/delete endpoints); DB-level DELETE/UPDATE revoked for app role; denied attempts logged; sensitive data never in `details`. |
| **Regression** | Existing Module 5 verification/audit/wills/beneficiaries/documents tests still pass; `manage.py check` clean; `makemigrations --check --dry-run` no unexpected changes. |

---

## 13. Technical Decisions & Recommendations

| Area | Decision | Rationale |
|------|----------|-----------|
| Google ID token verification | `google-auth` library (official) | Maintained, lightweight, handles JWKS caching, clock skew |
| Google account linking | Option A: `User.google_sub` field | Minimal migration; sufficient for single provider |
| Lawyer will access endpoint | New `/wills/<pk>/lawyer-view/` with `IsAssignedLawyerOnAuthorizedCase` | Clean separation from owner endpoints; anti-enumeration via 404 |
| Beneficiary allocation model | `BeneficiaryAllocation` with CheckConstraints | Enforces data integrity at DB level; flexible for SL inheritance |
| Release tracking | Dedicated `BeneficiaryRelease` model (not Boolean) | Supports partial release, withheld, retry, audit, multiple cases |
| Release authorization | Separate from verification decision; explicit action | Prevents accidental release; supports withholding |
| Notification reliability | Transactional outbox (`NotificationOutbox` model) | Atomic with release auth; retryable; no lost/duplicate emails |
| Release access token | SHA-256 hashed, single-use, 30-day TTL | Secure at rest; prevents replay; short window |
| Audit immutability | DB-level `REVOKE DELETE/UPDATE` for app role | Defense-in-depth beyond application logic |
| Currency | Explicit `currency` field, default `SLL` | No assumption of USD; Sierra Leone Leones |

---

## 14. Unresolved Questions — Blocking Implementation

### 14.1 Policy Questions (Supervisor Approval Required)
| ID | Question | Options | Impact |
|----|----------|---------|--------|
| **[B1]** | Lawyer will-access scope: pre-death, post-death, or both? | 1) Pre-death only (reuse disclosure)<br>2) Post-death only (new endpoint)<br>3) Both | Determines `AUTHORIZED_STATUSES`, new endpoints, whether pre-death disclosure gate is removed |
| **[B2]** | Lawyer document download permitted? | Yes / No | Adds download permission check to `WillDocumentDownloadAPIView` |
| **[C]** | AuditEvent DB-level immutability enforced? | Yes (REVOKE DELETE/UPDATE) / No (app-level only) | Deployment hardening |
| **[E1]** | Who can authorize beneficiary release? | Admin only / Assigned Lawyer / Both | Permission on `/authorize-release/` endpoint |
| **[E2]** | Does APPROVED mean all beneficiaries released? | Yes (all) / No (partial/withheld allowed) | `BeneficiaryRelease` creation logic; `Allocation.release_status=WITHHELD` support |
| **[E3]** | Can PRE_DEATH_REVIEW trigger beneficiary release? | Yes / No (likely No) | Release authorization gating |
| **[E4]** | Multiple verification cases per will → release per case? | Yes (each case independent) / No (latest only) | `BeneficiaryRelease` FK design |

### 14.2 Legal Questions (Qualified Sierra Leone Counsel Required)
| ID | Question | Reference |
|----|----------|-----------|
| **[LEGAL F1]** | What allocation structures are recognized in Sierra Leone (fixed amounts, percentages, specific items, contingent)? | `BeneficiaryAllocation` model design |
| **[LEGAL F2]** | Can a beneficiary's allocation be withheld post-verification (e.g., for debts, minority)? | `WITHHELD` release status |
| **[LEGAL F3]** | What identity verification is required for beneficiary access (email only, SMS, ID document)? | New beneficiary binding flow |
| **[LEGAL B1]** | Does pre-death legal review have binding effect on will execution? | Determines if pre-death approval can trigger release |
| **[LEGAL E1]** | What constitutes "authorized release conditions" under Sierra Leone law? | Release authorization gating |

---

## 15. Decisions Blocking Implementation (Concise List)

**Cannot begin implementation until resolved:**

1. **[B1]** Lawyer will-access scope (pre-death / post-death / both) — defines authorization logic, endpoints, and whether owner-disclosure safeguard is removed.
2. **[B2]** Lawyer document download permitted? — adds permission check.
3. **[C]** AuditEvent DB-level immutability enforcement? — deployment requirement.
4. **[E1]** Who authorizes release (Admin only / Lawyer / Both)? — permission on authorize-release endpoint.
5. **[E2]** Partial release / withheld allocations allowed? — `BeneficiaryRelease` and `Allocation` logic.
6. **[E3]** Pre-death review can trigger release? — release gating.
7. **[LEGAL F1–F3]** Sierra Leone inheritance allocation structures, withholding rules, identity verification — data model and binding flow.
8. **[LEGAL B1]** Pre-death review legal effect — release gating.
9. **[LEGAL E1]** Legal definition of "authorized release conditions" — authorization logic.

**Implementation can proceed in parallel for non-blocking items** (Google auth library choice, notification outbox, allocation model constraints) **once [B1], [E1], [E2] are resolved**, as they define core API contracts.

---

## 16. Recommended Implementation Order (Post-Approval)

1. **Database Migrations** (additive only): `User.google_sub`, `BeneficiaryAllocation`, `BeneficiaryRelease`, `NotificationOutbox`, `AuditEvent` EventTypes, `VerificationCase.release_authorized_*`.
2. **Google Auth (A):** Backend `google-auth` verification + `/google/login/`, `/google/link/`, `/google/unlink/`; frontend GIS SDK button.
3. **Lawyer Read-Only (B):** `IsAssignedLawyerOnAuthorizedCase` permission + `/wills/<pk>/lawyer-view/` + `/wills/<pk>/lawyer-documents/` (scope per [B1]).
4. **Lawyer Audit Trail (C):** Emit new `AuditEvent` types on all lawyer actions; admin audit list endpoint.
5. **Beneficiary Notification Policy (D):** Remove `send_beneficiary_invitation_email` from create/edit/resend paths.
6. **Release Authorization & Notification (E):** `/authorize-release/` endpoint (per [E1]); `BeneficiaryRelease` creation; `NotificationOutbox` + background sender; release token generation.
7. **Beneficiary Account Binding (E):** `/beneficiary-release/validate-token/`, `/claim/`; registration + email verification flow.
8. **Allocation View (F):** `/me/beneficiary-allocations/` + detail; serializer scoped to own relationships.
9. **Tests + Review:** Full test suite per §12; supervisor approval before Module 6.

---

**STOP**

**Do not write production code during this phase.** This document is for review and approval. Implement only after supervisor sign-off on the policy questions in §14.1 and legal questions in §14.2. Module 6 must not begin until the revised workflow is implemented, tested, and approved.
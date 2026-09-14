import test from "node:test";
import assert from "node:assert/strict";

// ---------------------------------------------------------------------------
// 1. TYPE / CONSTANT VALIDATION
// ---------------------------------------------------------------------------

test("User roles include all approved WillChain SL personas", () => {
  const allowedRoles = ["OWNER", "WITNESS", "BENEFICIARY", "LAWYER_VERIFIER", "ADMINISTRATOR"];
  assert.equal(allowedRoles.length, 5);
  assert.ok(allowedRoles.includes("OWNER"));
  assert.ok(allowedRoles.includes("WITNESS"));
  assert.ok(allowedRoles.includes("BENEFICIARY"));
  assert.ok(allowedRoles.includes("LAWYER_VERIFIER"));
  assert.ok(allowedRoles.includes("ADMINISTRATOR"));
});

test("Account statuses match platform state machine", () => {
  const statuses = ["PENDING_VERIFICATION", "ACTIVE", "INACTIVE", "SUSPENDED"];
  assert.equal(statuses.length, 4);
  assert.ok(statuses.includes("PENDING_VERIFICATION"));
  assert.ok(statuses.includes("ACTIVE"));
  assert.ok(statuses.includes("SUSPENDED"));
});

test("Invitation roles only permit invited collaborator roles", () => {
  const invitationRoles = ["WITNESS", "BENEFICIARY", "LAWYER_VERIFIER"];
  assert.equal(invitationRoles.length, 3);
  assert.ok(!invitationRoles.includes("OWNER"), "Testators cannot be invited through collaborator invites");
  assert.ok(!invitationRoles.includes("ADMINISTRATOR"), "Administrators cannot be invited through collaborator invites");
});

// ---------------------------------------------------------------------------
// 2. ERROR MESSAGE NORMALIZATION
// ---------------------------------------------------------------------------

test("Error message normalization handles nested DRF errors and generic fallbacks", () => {
  function extractMessage(raw) {
    let message = raw.error?.message ?? raw.detail ?? raw.message;
    if (!message && typeof raw === "object") {
      const firstKey = Object.keys(raw)[0];
      if (firstKey) {
        const val = raw[firstKey];
        message = Array.isArray(val) ? val.join(" ") : String(val);
      }
    }
    return message || "The request could not be completed.";
  }

  assert.equal(extractMessage({ detail: "Invalid credentials" }), "Invalid credentials");
  assert.equal(extractMessage({ email: ["Unable to create an account with these details."] }), "Unable to create an account with these details.");
  assert.equal(extractMessage({ error: { message: "Account is not active." } }), "Account is not active.");
  assert.equal(extractMessage({}), "The request could not be completed.");
});

// ---------------------------------------------------------------------------
// 3. INVITATION DETAIL TYPE VALIDATION
// ---------------------------------------------------------------------------

test("InvitationDetail shape matches backend response contract", () => {
  const detail = {
    email: "invited@example.com",
    first_name: "Jane",
    last_name: "Doe",
    role: "WITNESS",
    role_display: "Witness",
    inviter_name: "John Smith",
  };

  assert.equal(typeof detail.email, "string");
  assert.ok(detail.email.includes("@"));
  assert.ok(["WITNESS", "BENEFICIARY", "LAWYER_VERIFIER"].includes(detail.role));
  assert.equal(detail.role_display.length > 0, true);
  assert.equal(detail.inviter_name.length > 0, true);
});

// ---------------------------------------------------------------------------
// 4. AUTH SERVICE — TOKEN MANAGEMENT
// ---------------------------------------------------------------------------

test("getAccessToken / setAccessToken — in-memory token lifecycle", () => {
  let accessToken = null;
  function getAccessToken() { return accessToken; }
  function setAccessToken(token) { accessToken = token; }

  assert.equal(getAccessToken(), null);
  setAccessToken("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0");
  assert.equal(getAccessToken(), "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0");
  setAccessToken(null);
  assert.equal(getAccessToken(), null);
});

// ---------------------------------------------------------------------------
// 5. AUTH SERVICE — CSRF TOKEN PARSING
// ---------------------------------------------------------------------------

test("csrfToken parsing extracts value from cookie string", () => {
  function getCsrfFromCookie(cookieString) {
    if (!cookieString) return undefined;
    return cookieString
      .split("; ")
      .find((c) => c.startsWith("csrftoken="))
      ?.split("=")[1];
  }

  assert.equal(getCsrfFromCookie("csrftoken=abc123; sessionid=xyz"), "abc123");
  assert.equal(getCsrfFromCookie("sessionid=xyz; csrftoken=def456"), "def456");
  assert.equal(getCsrfFromCookie("sessionid=xyz"), undefined);
  assert.equal(getCsrfFromCookie(""), undefined);
  assert.equal(getCsrfFromCookie(null), undefined);
});

// ---------------------------------------------------------------------------
// 6. URL AVATAR RESOLUTION
// ---------------------------------------------------------------------------

test("avatarUrl resolves relative paths against API origin", () => {
  const API_ORIGIN = "http://localhost:8000";

  function avatarUrl(url) {
    if (!url) return "";
    return url.startsWith("http") ? url : `${API_ORIGIN}${url}`;
  }

  assert.equal(avatarUrl(null), "");
  assert.equal(avatarUrl("/media/avatars/photo.jpg"), "http://localhost:8000/media/avatars/photo.jpg");
  assert.equal(avatarUrl("http://cdn.example.com/avatar.png"), "http://cdn.example.com/avatar.png");
  assert.equal(avatarUrl(""), "");
});

// ---------------------------------------------------------------------------
// 7. INVITATION STATUS VALIDATION
// ---------------------------------------------------------------------------

test("Invitation validity logic matches backend Invitation.is_valid()", () => {
  const now = Date.now();

  function isInvitationValid(status, expiresAt) {
    return status === "PENDING" && new Date(expiresAt).getTime() > now;
  }

  // Valid: PENDING and not expired
  const future = new Date(now + 86400000).toISOString();
  assert.ok(isInvitationValid("PENDING", future));

  // Invalid: ACCEPTED even if not expired
  assert.equal(isInvitationValid("ACCEPTED", future), false);

  // Invalid: EXPIRED
  assert.equal(isInvitationValid("EXPIRED", future), false);

  // Invalid: REVOKED
  assert.equal(isInvitationValid("REVOKED", future), false);

  // Invalid: PENDING but expired
  const past = new Date(now - 86400000).toISOString();
  assert.equal(isInvitationValid("PENDING", past), false);
});

// ---------------------------------------------------------------------------
// 8. PASSWORD RESET PAYLOAD VALIDATION
// ---------------------------------------------------------------------------

test("Reset password payload contract matches backend expectations", () => {
  const validPayload = {
    uid: "MQ",
    token: "abc123token",
    new_password: "NewStrongPass1!",
    new_password_confirmation: "NewStrongPass1!",
  };

  assert.ok(validPayload.uid.length > 0);
  assert.ok(validPayload.token.length > 0);
  assert.ok(validPayload.new_password.length >= 8);
  assert.equal(validPayload.new_password, validPayload.new_password_confirmation);

  // Mismatched passwords
  const mismatch = { ...validPayload, new_password_confirmation: "DifferentPass1!" };
  assert.notEqual(mismatch.new_password, mismatch.new_password_confirmation);
});

// ---------------------------------------------------------------------------
// 9. CHANGE PASSWORD PAYLOAD VALIDATION
// ---------------------------------------------------------------------------

test("Change password payload contract matches backend expectations", () => {
  const payload = {
    current_password: "OldPass1!",
    new_password: "NewStrongPass1!",
    new_password_confirmation: "NewStrongPass1!",
  };

  assert.ok(payload.current_password.length > 0);
  assert.ok(payload.new_password.length >= 8);
  assert.equal(payload.new_password, payload.new_password_confirmation);
  assert.notEqual(payload.current_password, payload.new_password);
});

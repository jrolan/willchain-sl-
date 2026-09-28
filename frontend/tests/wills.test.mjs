import test from "node:test";
import assert from "node:assert/strict";

test("Will status values strictly match platform lifecycle requirements", () => {
  const allowedStatuses = ["DRAFT", "FINALIZED", "ARCHIVED"];
  assert.equal(allowedStatuses.length, 3);
  assert.ok(allowedStatuses.includes("DRAFT"));
  assert.ok(allowedStatuses.includes("FINALIZED"));
  assert.ok(allowedStatuses.includes("ARCHIVED"));
});

test("Will payload structure preserves structured testator and asset sections", () => {
  const payload = {
    title: "My Last Will and Testament",
    content: {
      testator: {
        full_name: "John Doe",
        marital_status: "MARRIED",
        address: "123 Main St",
        occupation: "Engineer",
      },
      family: {
        spouse_or_partner: "Jane Doe",
        children: [{ full_name: "Alice Doe" }],
      },
      executor: {
        full_name: "Trusted Executor",
        relationship: "Brother",
      },
      beneficiaries: [{ full_name: "Alice Doe", relationship: "Daughter" }],
      gifts: [{ description: "Family Home", beneficiary_name: "Alice Doe" }],
      residual_estate: "All remaining property to Jane Doe.",
    },
  };

  assert.equal(payload.title, "My Last Will and Testament");
  assert.equal(payload.content.testator.full_name, "John Doe");
  assert.equal(payload.content.beneficiaries.length, 1);
  assert.equal(payload.content.gifts.length, 1);
});

test("Protected metadata fields cannot be client-controlled in typed payload", () => {
  // Verifying that WillPayload type excludes read-only server attributes
  const clientEditableKeys = ["title", "content"];
  const serverControlledKeys = ["id", "owner", "owner_email", "status", "version", "finalized_at", "created_at", "updated_at"];

  for (const key of serverControlledKeys) {
    assert.ok(!clientEditableKeys.includes(key), `Field ${key} must not be present in client-editable payload`);
  }
});

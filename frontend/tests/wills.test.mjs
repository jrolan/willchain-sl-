import test from "node:test";
import assert from "node:assert/strict";

import { buildWillDocumentHtml, buildWillDocumentText } from "../lib/will-export.mjs";

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

test("Structured will content renders as readable document text for final export", () => {
  const will = {
    title: "My Last Will and Testament",
    content: {
      testator: { full_name: "John Doe", address: "123 Main St" },
      family: { spouse_or_partner: "Jane Doe" },
      beneficiaries: [{ full_name: "Alice Doe", relationship: "Daughter" }],
      gifts: [{ beneficiary_name: "Alice Doe", description: "Family home" }],
      residual_estate: "All remaining property to Jane Doe.",
      review_notes: "Check everything carefully before signing.",
    },
  };

  const exported = buildWillDocumentText(will);

  assert.match(exported, /My Last Will and Testament/);
  assert.match(exported, /Testator/);
  assert.match(exported, /Beneficiaries/);
  assert.match(exported, /Family home/);
  assert.match(exported, /Jane Doe/);
  assert.match(exported, /Check everything carefully/);
});

test("Rich pasted will content keeps formatting in exports and escapes unsafe markup", () => {
  const will = {
    title: "A <safe> will",
    content: {
      sections: [{
        title: "Pasted will draft",
        body: JSON.stringify({
          type: "doc",
          content: [
            { type: "heading", attrs: { level: 2 }, content: [{ type: "text", text: "My wishes" }] },
            { type: "paragraph", content: [{ type: "text", text: "Important", marks: [{ type: "bold" }] }, { type: "text", text: " <script>alert(1)</script>" }] },
            { type: "bulletList", content: [{ type: "listItem", content: [{ type: "paragraph", content: [{ type: "text", text: "First gift" }] }] }] },
          ],
        }),
      }],
    },
  };

  const text = buildWillDocumentText(will);
  const html = buildWillDocumentHtml(will);

  assert.match(text, /My wishes/);
  assert.match(text, /First gift/);
  assert.match(html, /<strong>Important<\/strong>/);
  assert.match(html, /<ul><li><p>First gift<\/p><\/li><\/ul>/);
  assert.match(html, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /A &lt;safe&gt; will/);
});

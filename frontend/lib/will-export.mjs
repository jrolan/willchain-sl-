function asText(value) {
  if (value === null || value === undefined || value === "") return "Not specified";
  if (typeof value === "string") return value.trim() || "Not specified";
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value, null, 2).replace(/[\r\n]+/g, " ");
}

function formatSection(title, entries) {
  const lines = [`${title}:`];
  for (const [key, value] of Object.entries(entries)) {
    if (!value && value !== 0) continue;
    const label = key.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
    if (Array.isArray(value)) {
      if (value.length === 0) continue;
      const items = value
        .map((item) => {
          if (typeof item === "string") return `- ${item}`;
          if (typeof item === "object" && item !== null) {
            const itemText = Object.entries(item)
              .filter(([, nestedValue]) => nestedValue !== undefined && nestedValue !== null && nestedValue !== "")
              .map(([nestedKey, nestedValue]) => `${nestedKey.replace(/_/g, " ")}: ${asText(nestedValue)}`)
              .join("; ");
            return `- ${itemText}`;
          }
          return `- ${asText(item)}`;
        })
        .join("\n");
      lines.push(`${label}:\n${items}`);
      continue;
    }
    if (typeof value === "object") {
      const nested = Object.entries(value)
        .filter(([, nestedValue]) => nestedValue !== undefined && nestedValue !== null && nestedValue !== "")
        .map(([nestedKey, nestedValue]) => `${nestedKey.replace(/_/g, " ")}: ${asText(nestedValue)}`)
        .join("; ");
      if (nested) lines.push(`${label}: ${nested}`);
      continue;
    }
    lines.push(`${label}: ${asText(value)}`);
  }
  return lines.join("\n");
}

function parseRichDocument(body) {
  if (typeof body !== "string") return null;
  try {
    const parsed = JSON.parse(body);
    return parsed?.type === "doc" && Array.isArray(parsed.content) ? parsed : null;
  } catch {
    return null;
  }
}

function richNodeText(node) {
  if (!node || typeof node !== "object") return "";
  if (node.type === "text") return String(node.text ?? "");
  if (node.type === "hardBreak") return "\n";
  const children = Array.isArray(node.content) ? node.content : [];
  if (node.type === "orderedList") {
    return children.map((item, index) => `${index + 1}. ${richNodeText(item).trim()}`).join("\n") + "\n";
  }
  if (node.type === "bulletList") {
    return children.map((item) => `- ${richNodeText(item).trim()}`).join("\n") + "\n";
  }
  const value = children.map(richNodeText).join("");
  if (["paragraph", "heading", "listItem", "blockquote", "codeBlock"].includes(node.type)) return `${value}\n`;
  if (node.type === "horizontalRule") return "\n";
  return value;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function richNodeHtml(node) {
  if (!node || typeof node !== "object") return "";
  if (node.type === "text") {
    let text = escapeHtml(node.text ?? "");
    for (const mark of node.marks ?? []) {
      if (mark.type === "bold") text = `<strong>${text}</strong>`;
      if (mark.type === "italic") text = `<em>${text}</em>`;
      if (mark.type === "underline") text = `<u>${text}</u>`;
      if (mark.type === "strike") text = `<s>${text}</s>`;
      if (mark.type === "code") text = `<code>${text}</code>`;
    }
    return text;
  }
  if (node.type === "hardBreak") return "<br />";
  if (node.type === "horizontalRule") return "<hr />";

  const children = (node.content ?? []).map(richNodeHtml).join("");
  if (node.type === "paragraph") return `<p>${children}</p>`;
  if (node.type === "heading") {
    const level = Math.min(6, Math.max(1, Number(node.attrs?.level) || 2));
    return `<h${level}>${children}</h${level}>`;
  }
  if (node.type === "bulletList") return `<ul>${children}</ul>`;
  if (node.type === "orderedList") return `<ol>${children}</ol>`;
  if (node.type === "listItem") return `<li>${children}</li>`;
  if (node.type === "blockquote") return `<blockquote>${children}</blockquote>`;
  if (node.type === "codeBlock") return `<pre><code>${children}</code></pre>`;
  return children;
}

function extraSectionText(sections) {
  return (sections ?? []).map((section) => {
    const title = asText(section?.title ?? "Additional will text");
    const richDocument = parseRichDocument(section?.body);
    const body = richDocument ? richNodeText(richDocument).trim() : asText(section?.body);
    return `${title}:\n${body}`;
  });
}

export function buildWillDocumentText(will) {
  const content = will?.content ?? {};
  const testator = content.testator ?? {};
  const family = content.family ?? {};
  const executor = content.executor ?? {};
  const sections = [
    `Will title: ${asText(will?.title)}`,
    `Status: ${asText(will?.status ?? "DRAFT")}`,
    "",
    "Testator",
    formatSection("Testator", testator),
    "",
    formatSection("Family", family),
    "",
    formatSection("Executor", executor),
    "",
    formatSection("Beneficiaries", { beneficiaries: content.beneficiaries ?? [] }),
    "",
    formatSection("Gifts", { gifts: content.gifts ?? [] }),
    "",
    `Residual estate: ${asText(content.residual_estate)}`,
    `Funeral wishes: ${asText(content.funeral_wishes)}`,
    `Digital assets notes: ${asText(content.digital_assets_notes)}`,
    `Review notes: ${asText(content.review_notes)}`,
    ...extraSectionText(content.sections),
    "",
    "Prepared in the WillChain platform.",
  ];

  return sections.join("\n").replace(/\n{3,}/g, "\n\n");
}

export function buildWillDocumentHtml(will) {
  const content = will?.content ?? {};
  const sections = Array.isArray(content.sections) ? content.sections : [];
  const text = buildWillDocumentText({ ...will, content: { ...content, sections: [] } });
  const html = text
    .split("\n")
    .map((line) => {
      const trimmed = line.trim();
      if (!trimmed) return "<br />";
      if (/^Will title:|^Status:|^Testator$|^Family$|^Executor$|^Beneficiaries$|^Gifts$/.test(trimmed)) {
        return `<p><strong>${escapeHtml(trimmed)}</strong></p>`;
      }
      return `<p>${escapeHtml(trimmed)}</p>`;
    })
    .join("");
  const richSections = sections.map((section) => {
    const title = escapeHtml(section?.title ?? "Additional will text");
    const richDocument = parseRichDocument(section?.body);
    const body = richDocument ? richNodeHtml(richDocument) : `<p>${escapeHtml(section?.body ?? "")}</p>`;
    return `<section><h2>${title}</h2>${body}</section>`;
  }).join("");

  return `<!doctype html><html><head><meta charset="utf-8" /><title>${escapeHtml(will?.title ?? "Will")}</title><style>body{font-family:Arial,sans-serif;max-width:900px;margin:40px auto;padding:0 32px;color:#1f2937;line-height:1.6}p{margin:0 0 8px}strong{color:#17372f}h1,h2,h3,h4,h5,h6{color:#17372f}blockquote{border-left:3px solid #2160f5;margin:12px 0;padding-left:12px}pre,code{background:#f1f5f9;padding:2px 4px}li{margin:4px 0}</style></head><body>${html}${richSections}</body></html>`;
}

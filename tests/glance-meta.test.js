const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");
function extractByFunctionName(name) {
  const m = source.slice(source.indexOf("function " + name));
  let i = m.indexOf("{"), depth = 0, end = -1;
  for (let j = i; j < m.length; j++) { if (m[j] === "{") depth++; if (m[j] === "}") { depth--; if (depth === 0) { end = j; break; } } }
  if (end === -1) throw new Error(`function ${name} not found`);
  return m.slice(0, end + 1);
}
const glanceMetaHtml = (0, eval)(`(${extractByFunctionName("glanceMetaHtml")})`);
const hl = (t) => t || "";

// 2026-09-21 (Joe's call): the glance card's third line collapsed from
// [domain tag] - date of action - verified date to a single "Last update: <date>".
test("glanceMetaHtml renders only a single Last update span, no domain tag or date of action", () => {
  const entry = { domain: "environmental", agency: "EPA", date_of_action: "2026-02-12", last_verified: "2026-09-12", last_substantive_update: "2026-08-01" };
  const html = glanceMetaHtml(entry, { kind: "deregulation" }, null, hl);
  assert.equal(html, '<span>Last update: 2026-08-01</span>');
  assert(!html.includes("domain-tag"));
  assert(!html.includes("EPA"));
  assert(!html.includes("2026-02-12"));
});

test("glanceMetaHtml prefers last_substantive_update over last_verified", () => {
  const entry = { last_verified: "2026-09-12", last_substantive_update: "2026-08-01" };
  assert.equal(glanceMetaHtml(entry, { kind: "govservices" }, null, hl), '<span>Last update: 2026-08-01</span>');
});

test("glanceMetaHtml falls back to last_verified when last_substantive_update is missing", () => {
  const entry = { last_verified: "2026-09-12" };
  assert.equal(glanceMetaHtml(entry, { kind: "prosecution" }, null, hl), '<span>Last update: 2026-09-12</span>');
});

test("glanceMetaHtml renders nothing when neither date is present", () => {
  assert.equal(glanceMetaHtml({}, { kind: "prosecution" }, null, hl), '');
});

test("glanceMetaHtml keeps the source-tag prefix (cross-database search context), unaffected by this change", () => {
  const entry = { last_verified: "2026-09-12" };
  const html = glanceMetaHtml(entry, { kind: "deregulation" }, "Deregulation", hl);
  assert.equal(html, '<span class="source-tag">Deregulation</span><span>Last update: 2026-09-12</span>');
});

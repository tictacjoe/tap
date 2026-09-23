const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function extractFunction(source, name) {
  const startMarker = `/* ${name}:start */`;
  const endMarker = `/* ${name}:end */`;
  const start = source.indexOf(startMarker);
  const end = source.indexOf(endMarker);
  if (start === -1 || end === -1) {
    throw new Error(`Markers for ${name} not found in index.html`);
  }
  return source.slice(start + startMarker.length, end);
}

const source = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");
// figureKindOf is only reached when an entry has figures; stubbed so the
// figure-suffix test does not drag in the whole figure classifier.
const stub = "function figureKindOf() { return 'harm'; }";
const combined =
  extractFunction(source, "escape-html") + "\n" +
  extractFunction(source, "highlight-matches") + "\n" +
  extractFunction(source, "glance-head") + "\n" +
  extractFunction(source, "visible-search-text") + "\n" +
  extractFunction(source, "one-liner-base") + "\n" +
  extractFunction(source, "one-liner-for") + "\n" + stub;
const api = (0, eval)(`${combined}\n({ visibleSearchText, oneLinerFor });`);

function validGlance(overrides = {}) {
  return {
    who: "Jane Example",
    what: "Ordered an example detention policy",
    harm: { kind: "rights", certainty: "alleged", who: "Example detainees" },
    reviewed: "2026-09-20",
    ...overrides,
  };
}
const cfgOn = { kind: "prosecution", titleField: "official", glanceEnabled: true };
const cfgOff = { kind: "prosecution", titleField: "official", glanceEnabled: false };

test("visibleSearchText includes the visible glance text when active", () => {
  const entry = { official: "Jane Example, Secretary", glance: validGlance() };
  const text = api.visibleSearchText(entry, cfgOn);
  assert.ok(text.includes("Ordered an example detention policy"));
  assert.ok(text.includes("Example detainees"));
  assert.ok(text.includes("Rights & liberty"));
});

test("visibleSearchText leaves glance text out when the flag is off", () => {
  const entry = { official: "Jane Example, Secretary", glance: validGlance() };
  assert.ok(!api.visibleSearchText(entry, cfgOff).includes("Ordered an example detention policy"));
});

test("oneLinerFor is unchanged for entries without an active glance", () => {
  const entry = { official: "Jane Example", status_category: "Indicted", offense_category: "Abuse", contested: false, glance: validGlance() };
  assert.equal(api.oneLinerFor(entry, cfgOff).line, "Jane Example — Indicted: Abuse");
});

test("oneLinerFor becomes who - what for an active glance", () => {
  const entry = { official: "Jane Example", glance: validGlance() };
  const result = api.oneLinerFor(entry, cfgOn);
  assert.equal(result.line, "Jane Example — Ordered an example detention policy");
  assert.equal(result.figure, null);
});

test("oneLinerFor keeps the figure suffix for an active glance", () => {
  const cfg = { kind: "deregulation", titleField: "rule_name", glanceEnabled: true };
  const entry = {
    rule_name: "Rule", agency: "EPA", status: "Fully repealed",
    estimated_health_impact: { figures: [{ metric: "Deaths", value: "10" }] },
    glance: validGlance(),
  };
  const result = api.oneLinerFor(entry, cfg);
  assert.equal(result.line, "Jane Example — Ordered an example detention policy");
  assert.equal(result.figure, "Deaths: 10.");
  assert.equal(result.figureKind, "harm");
});

const cfgDereg = { kind: "deregulation", titleField: "rule_name", glanceEnabled: true };
const cfgDeregOff = { kind: "deregulation", titleField: "rule_name", glanceEnabled: false };
const deregEntry = () => ({
  rule_name: "Rule", agency: "Example Agency of Testing", short_summary: "Zorblax wording only in the summary",
  glance: validGlance(),
});

test("visibleSearchText for Deregulation leaves short_summary out but keeps agency when glance is active", () => {
  const text = api.visibleSearchText(deregEntry(), cfgDereg);
  assert.ok(!text.includes("Zorblax"));
  assert.ok(text.includes("Example Agency of Testing"));
});

test("visibleSearchText for Deregulation still includes short_summary when the flag is off", () => {
  const text = api.visibleSearchText(deregEntry(), cfgDeregOff);
  assert.ok(text.includes("Zorblax"));
  assert.ok(text.includes("Example Agency of Testing"));
});

// GSR/CDR Broader Pattern is visible on the expanded card (2026-09-23 spec,
// sec-5 item 3), so this function's own rule puts it in the haystack.
for (const kind of ["govservices", "deregulation"]) {
  test(`visibleSearchText includes cause for ${kind} (Broader Pattern card is visible)`, () => {
    const entry = { title: "T", rule_name: "T", cause: "[TAP Analysis, not sourced] zebra pattern" };
    assert.ok(api.visibleSearchText(entry, { kind, titleField: "title" }).includes("zebra pattern"));
  });
}

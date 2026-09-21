const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function extractFunction(source, name) {
  const startMarker = `/* ${name}:start */`;
  const endMarker = `/* ${name}:end */`;
  const start = source.indexOf(startMarker);
  const end = source.indexOf(endMarker);
  if (start === -1 || end === -1) throw new Error(`Markers for ${name} not found in index.html`);
  return source.slice(start + startMarker.length, end);
}

const source = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");
globalThis.location = { href: "https://example.test/" };
const api = (0, eval)(
  extractFunction(source, "escape-html") + "\n" +
  extractFunction(source, "safe-href") + "\n" +
  extractFunction(source, "evidence-drawer") + "\n" +
  "({ CLAIM_STATE_LABELS, CLAIM_STATE_SHORT, EVIDENCE_NOTE_TEXT, EVIDENCE_UNAVAILABLE_TEXT, claimStateOf, " +
  "evidenceTallyText, claimShortDate, evidenceHostOf, buildEvidenceItemHtml, buildEvidenceItemsHtml, " +
  "buildEvidenceDrawerHtml });");

const hl = (text) => text || "";
const ITEM = { type: "news_report", description: "CNN reporting on the ruling", source_url: "https://www.npr.org/story" };
const check = (over) => ({ state: "supports", why: "The page states it.", host: "npr.org", date: "2026-09-15", kind: "fact", archive: false, ...over });
const ENTRY = { id: "entry-a", evidence: [ITEM, { ...ITEM, description: "second" }, { ...ITEM, description: "third" }] };
const CFG = { evidenceDrawerEnabled: true };

test("state labels are exactly the approved wording", () => {
  assert.deepEqual(api.CLAIM_STATE_LABELS, {
    supports: "Source supports the main assertion",
    partly: "Source supports part of the claim",
    not_found: "Claim not found on this page",
    unopened: "Couldn't open this source automatically",
    differs: "Source differs from the description",
    unchecked: "Not yet checked",
  });
});

test("the drawer chrome text never says 'verified'", () => {
  const chrome = [...Object.values(api.CLAIM_STATE_LABELS), ...Object.values(api.CLAIM_STATE_SHORT),
    api.EVIDENCE_NOTE_TEXT, api.EVIDENCE_UNAVAILABLE_TEXT];
  for (const text of chrome) assert(!/verified/i.test(text), text);
});

test("claimStateOf falls back to unchecked for a missing or unknown check", () => {
  assert.equal(api.claimStateOf({ "0": check() }, 0), "supports");
  assert.equal(api.claimStateOf({ "0": check() }, 1), "unchecked");
  assert.equal(api.claimStateOf({ "0": check({ state: "bogus" }) }, 0), "unchecked");
  assert.equal(api.claimStateOf(null, 0), "unchecked");
});

test("evidenceTallyText counts states in the fixed order and omits zeros", () => {
  const checks = { "0": check(), "1": check({ state: "partly" }), "2": check({ state: "supports" }) };
  assert.equal(api.evidenceTallyText(5, checks), "2 support · 1 partly · 2 not yet checked");
  assert.equal(api.evidenceTallyText(2, {}), "2 not yet checked");
  assert.equal(api.evidenceTallyText(3, null), "");
});

test("claimShortDate formats ISO dates and rejects bad input", () => {
  assert.equal(api.claimShortDate("2026-09-15"), "Sep 15, 2026");
  assert.equal(api.claimShortDate("2026-01-03"), "Jan 3, 2026");
  assert.equal(api.claimShortDate("nonsense"), "");
  assert.equal(api.claimShortDate(""), "");
});

test("evidenceHostOf strips www and survives a bad URL", () => {
  assert.equal(api.evidenceHostOf("https://www.NPR.org/a"), "npr.org");
  assert.equal(api.evidenceHostOf("not a url"), "");
});

test("a supports item shows badge, description, checked-against line and a Why toggle", () => {
  const html = api.buildEvidenceItemHtml(ITEM, 0, check(), hl);
  assert(html.includes("Source supports the main assertion"));
  assert(html.includes('<span class="evidence-glyph" aria-hidden="true">'));
  assert(html.includes("CNN reporting on the ruling"));
  assert(html.includes('href="https://www.npr.org/story" target="_blank" rel="noopener">npr.org</a>'));
  assert(html.includes("Checked against"));
  assert(html.includes(", Sep 15, 2026"));
  assert(!html.includes("archived copy"));
  assert(html.includes('<details class="evidence-why-toggle"><summary>Why</summary>'));
});

test("partly, not_found, unopened and differs show their reasoning openly, not in a toggle", () => {
  for (const state of ["partly", "not_found", "unopened", "differs"]) {
    const html = api.buildEvidenceItemHtml(ITEM, 0, check({ state, why: "the detail is missing" }), hl);
    assert(html.includes('<p class="evidence-why">the detail is missing</p>'), state);
    assert(!html.includes("<details"), state);
  }
});

test("an archived-copy check says so, and an interpretation is tagged", () => {
  const html = api.buildEvidenceItemHtml(ITEM, 0, check({ archive: true, kind: "interpretation" }), hl);
  assert(html.includes("(archived copy)"));
  assert(html.includes('<span class="evidence-tag">Interpretation</span>'));
});

test("an item with no check reads 'Not yet checked' with a plain source link", () => {
  const html = api.buildEvidenceItemHtml(ITEM, 0, undefined, hl);
  assert(html.includes("Not yet checked"));
  assert(html.includes("Source: "));
  assert(!html.includes("Checked against"));
  assert(html.includes("evidence-state-unchecked"));
});

test("host and dates from the data are escaped, and an unsafe source URL becomes #", () => {
  const html = api.buildEvidenceItemHtml({ ...ITEM, source_url: "javascript:alert(1)" }, 0,
    check({ host: '"><img src=x>' }), hl);
  assert(!html.includes("<img"));
  assert(html.includes('href="#"'));
});

test("the entry's description goes through the hl function it is given", () => {
  const html = api.buildEvidenceItemHtml(ITEM, 0, check(), (t) => t.toUpperCase());
  assert(html.includes("CNN REPORTING ON THE RULING"));
});

test("no drawer when the flag is off, there is no evidence, or evidence is not a list", () => {
  assert.equal(api.buildEvidenceDrawerHtml(ENTRY, {}, hl), "");
  assert.equal(api.buildEvidenceDrawerHtml(ENTRY, { evidenceDrawerEnabled: false }, hl), "");
  assert.equal(api.buildEvidenceDrawerHtml({ id: "x", evidence: [] }, CFG, hl), "");
  assert.equal(api.buildEvidenceDrawerHtml({ id: "x" }, CFG, hl), "");
  assert.equal(api.buildEvidenceDrawerHtml({ id: "x", evidence: "nope" }, CFG, hl), "");
});

test("the drawer starts collapsed with an accessible button and no tally before the first open", () => {
  const html = api.buildEvidenceDrawerHtml(ENTRY, CFG, hl);
  assert(html.includes('aria-expanded="false"'));
  const controls = /aria-controls="([^"]+)"/.exec(html)[1];
  assert(html.includes(`id="${controls}" hidden`));
  assert(html.includes("Evidence · 3 items"));
  assert(html.includes('<span class="evidence-tally"></span>'));
  assert(html.includes(api.EVIDENCE_NOTE_TEXT));
  assert(html.includes('href="docs/tap-source-check-method.html"'));
  assert(api.buildEvidenceDrawerHtml({ id: "one", evidence: [ITEM] }, CFG, hl).includes("Evidence · 1 item<"));
});

test("after the checks load, the tally and states appear", () => {
  const html = api.buildEvidenceDrawerHtml(ENTRY, CFG, hl,
    { loadState: "loaded", checks: { "0": check(), "1": check({ state: "unopened" }) } });
  assert(html.includes('<span class="evidence-tally">1 support · 1 couldn\'t open · 1 not yet checked</span>'));
  assert(html.includes("Couldn't open this source automatically"));
});

test("when the check file cannot be loaded the items still list, with the unavailable notice", () => {
  const html = api.buildEvidenceDrawerHtml(ENTRY, CFG, hl, { loadState: "failed", checks: null });
  assert(html.includes(api.EVIDENCE_UNAVAILABLE_TEXT));
  assert.equal((html.match(/class="evidence-item /g) || []).length, 3);
  assert(html.includes("Not yet checked"));
});

test("an entry id is sanitized for the element id and escaped in the data attribute", () => {
  const html = api.buildEvidenceDrawerHtml({ id: 'a b"c<d', evidence: [ITEM] }, CFG, hl);
  assert(/id="evidence-a-b-c-d-body"/.test(html));
  assert(!html.includes('"c<d'));
  assert(html.includes('data-evidence-entry="a b&quot;c&lt;d"'));
});

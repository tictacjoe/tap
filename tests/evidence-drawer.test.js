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
  "buildEvidenceDrawerHtml, isRecheckNote });");

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

// The source line has to match the label: nothing was checked against a page the
// software could not open, so an unopened item says what actually happened.
test("an unopened item says 'Tried', not 'Checked against'", () => {
  const html = api.buildEvidenceItemHtml(ITEM, 0, check({ state: "unopened", why: "" }), hl);
  assert(html.includes('Tried <a href="https://www.npr.org/story"'), html);
  assert(html.includes(", Sep 15, 2026"));
  assert(!html.includes("Checked against"));
  const archived = api.buildEvidenceItemHtml(ITEM, 0, check({ state: "unopened", archive: true }), hl);
  assert(archived.includes("Tried ") && archived.includes("(archived copy)"));
});

test("every state where the page was read still says 'Checked against'", () => {
  for (const state of ["supports", "partly", "not_found", "differs"]) {
    const html = api.buildEvidenceItemHtml(ITEM, 0, check({ state }), hl);
    assert(html.includes("Checked against "), state);
    assert(!html.includes("Tried "), state);
  }
});

// CLAIM_STATE_LABELS is a plain object, so "constructor" and friends are truthy
// on it by inheritance; a check carrying one must still read as unchecked.
test("a check whose state is an inherited property name renders as unchecked", () => {
  assert.equal(api.claimStateOf({ "0": check({ state: "constructor" }) }, 0), "unchecked");
  const html = api.buildEvidenceItemHtml(ITEM, 0, check({ state: "constructor" }), hl);
  assert(html.includes("evidence-state-unchecked"), html.slice(0, 200));
  assert(html.includes("Not yet checked"));
  assert(!html.includes("function Object"));
});

// --- TAP's own recheck notes are not sources: the drawer leaves them out -------------------
// (decision 2026-09-21). Checks stay keyed by an item's ORIGINAL position in entry.evidence,
// so skipping a note never renumbers the items after it.
const NOTE = (text) => ({ type: "note", description: text, source_url: "" });
const REAL = (text, over) => ({ ...ITEM, description: text, ...over });

test("isRecheckNote matches 'Re-verified' and 'Re-verification' at the start only", () => {
  assert.equal(api.isRecheckNote(NOTE("Re-verified 2026-08-18: no new litigation resolution.")), true);
  assert.equal(api.isRecheckNote(NOTE("  re-verification 2026-08-20 found no change.")), true);
  assert.equal(api.isRecheckNote(NOTE("Added 2026-08-01 (fold): a real source's description.")), false);
  assert.equal(api.isRecheckNote(REAL("The ruling was re-verified by two outlets.")), false);
  assert.equal(api.isRecheckNote(NOTE("Re-verifying the docket later.")), false);
  assert.equal(api.isRecheckNote({}), false);
  assert.equal(api.isRecheckNote(null), false);
  assert.equal(api.isRecheckNote(undefined), false);
});

test("the drawer skips recheck notes but keeps the original position for the check lookup", () => {
  const entry = { id: "e", evidence: [
    NOTE("Re-verified 2026-08-18: nothing new."), NOTE("Re-verification 2026-08-19: nothing new."),
    REAL("first source"), REAL("second source"), NOTE("Re-verified 2026-08-20: still nothing."),
  ] };
  // Checks keyed by ORIGINAL position: 2 -> first source, 3 -> second source; 0 is a note's.
  const html = api.buildEvidenceDrawerHtml(entry, CFG, hl,
    { loadState: "loaded", checks: { "0": check({ state: "partly" }), "2": check({ state: "supports" }), "3": check({ state: "unopened", why: "" }) } });
  assert.equal((html.match(/class="evidence-item /g) || []).length, 2);
  assert(!html.includes("Re-verif"));
  const items = html.split('<li ').slice(1);
  assert(items[0].includes("first source") && items[0].includes("evidence-state-supports"), items[0]);
  assert(items[1].includes("second source") && items[1].includes("evidence-state-unopened"), items[1]);
});

test("the header count and the tally count listed items only", () => {
  const entry = { id: "e", evidence: [
    NOTE("Re-verified 2026-08-18: nothing new."), REAL("a"), REAL("b"), NOTE("Re-verification 2026-08-19: nothing new."),
  ] };
  const collapsed = api.buildEvidenceDrawerHtml(entry, CFG, hl);
  assert(collapsed.includes("Evidence · 2 items"), collapsed);
  // The note's own check (position 0, "partly") must not reach the tally.
  const html = api.buildEvidenceDrawerHtml(entry, CFG, hl,
    { loadState: "loaded", checks: { "0": check({ state: "partly" }), "1": check(), "2": check({ state: "unopened" }) } });
  assert(html.includes('<span class="evidence-tally">1 support · 1 couldn\'t open</span>'), html);
  // One listed item reads "1 item".
  const one = { id: "o", evidence: [NOTE("Re-verified 2026-08-18: nothing new."), REAL("only")] };
  assert(api.buildEvidenceDrawerHtml(one, CFG, hl).includes("Evidence · 1 item<"));
});

test("evidenceTallyText takes an optional list of listed positions and defaults to all", () => {
  const checks = { "0": check({ state: "partly" }), "1": check(), "2": check() };
  assert.equal(api.evidenceTallyText(3, checks), "2 support · 1 partly");
  assert.equal(api.evidenceTallyText(3, checks, [1, 2]), "2 support");
  assert.equal(api.evidenceTallyText(3, checks, [0, 1, 2]), "2 support · 1 partly");
  assert.equal(api.evidenceTallyText(3, null, [1]), "");
});

test("a mid-text 're-verified' is not a note, so that item is listed", () => {
  const entry = { id: "e", evidence: [REAL("Court records show the order was re-verified in May.")] };
  const html = api.buildEvidenceDrawerHtml(entry, CFG, hl);
  assert(html.includes("Evidence · 1 item<"));
  assert.equal((html.match(/class="evidence-item /g) || []).length, 1);
});

test("an entry whose evidence is all recheck notes gets no drawer", () => {
  const entry = { id: "e", evidence: [NOTE("Re-verified 2026-08-18: nothing new."), NOTE("Re-verification 2026-08-19: nothing new.")] };
  assert.equal(api.buildEvidenceDrawerHtml(entry, CFG, hl), "");
  assert.equal(api.buildEvidenceDrawerHtml(entry, CFG, hl, { loadState: "loaded", checks: {} }), "");
});

test("an entry with no recheck notes renders exactly as before", () => {
  const checks = { "0": check(), "1": check({ state: "partly", why: "part" }) };
  const html = api.buildEvidenceDrawerHtml(ENTRY, CFG, hl, { loadState: "loaded", checks });
  assert(html.includes("Evidence · 3 items"));
  assert(html.includes('<span class="evidence-tally">1 support · 1 partly · 1 not yet checked</span>'));
  const items = html.split('<li ').slice(1);
  assert.equal(items.length, 3);
  assert(items[0].includes("CNN reporting") && items[1].includes("second") && items[2].includes("third"));
});

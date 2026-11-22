// Harms list (2026-11-16, spec tap-data docs/superpowers/specs/2026-11-16-harms-list-design.md):
// every curated entry's Glance "Harm to" value, grouped by harm kind, then
// certainty, each line linking back to its entry.
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
const combined =
  extractFunction(source, "escape-html") + "\n" +
  extractFunction(source, "highlight-matches") + "\n" +
  extractFunction(source, "violation-concern-value") + "\n" +
  extractFunction(source, "glance-head") + "\n" +
  extractFunction(source, "harms-list");
const api = (0, eval)(`${combined}\n({ collectHarms, buildHarmsListHtml });`);

const ABBR = { prosecution: "CLA", govservices: "GSR", dai: "DAI", tracker: "RPT" };

function entry(id, harm, what = "Did an example thing") {
  return {
    id,
    glance: {
      who: "Example official",
      what,
      harm: { kind: "rights", certainty: "documented", who: "Example detainees", ...harm },
      reviewed: "2026-09-20",
    },
  };
}

function trackersWith(prosecutionData, extra = {}) {
  return {
    prosecution: { idField: "id", glanceEnabled: true, data: prosecutionData },
    ...extra,
  };
}

test("collectHarms skips invalid glance, glanceEnabled false, hidden trackers, Reporting and Community Topics", () => {
  const bad = { id: "bad", glance: { who: "x" } };
  const trackers = {
    prosecution: { idField: "id", glanceEnabled: true, data: [entry("p1", {}), bad, { id: "noglance" }] },
    govservices: { idField: "id", glanceEnabled: true, data: [entry("g1", { kind: "money" })] },
    deregulation: { idField: "id", glanceEnabled: false, data: [entry("d1", {})] },
    dai: { idField: "id", glanceEnabled: true, hidden: true, data: [entry("h1", {})] },
    tracker: { idField: "id", glanceEnabled: true, data: [entry("r1", {})] },
    communitytopics: { idField: "id", glanceEnabled: true, data: [entry("c1", {})] },
  };
  const ids = api.collectHarms(trackers).map(r => r.id).sort();
  assert.deepEqual(ids, ["g1", "p1"]);
  const p1 = api.collectHarms(trackers).find(r => r.id === "p1");
  assert.deepEqual(p1, { key: "prosecution", id: "p1", kind: "rights", certainty: "documented", who: "Example detainees", what: "Did an example thing", tier: null });
});

// First-principle grouping (2026-11-19, spec tap-data
// docs/superpowers/specs/2026-11-19-harms-first-principle-design.md):
// 1 life and health, 2 money harm that puts life or health at risk, 3 money,
// then Other harms by kind. glance.harm.tier overrides the kind's default.
const tiersIn = html => [...html.matchAll(/data-tier="([a-z0-9]+)"/g)].map(m => m[1]);
const section = (html, attr) => {
  const start = html.indexOf(attr);
  if (start === -1) return "";
  const next = html.indexOf('<section class="harms-tier"', start + 1);
  return html.slice(start, next === -1 ? html.length : next);
};

test("tiers render 1, 2, 3, other with verbatim labels and empty tiers omitted", () => {
  const html = api.buildHarmsListHtml(trackersWith([
    entry("a", { kind: "institutional" }),
    entry("b", { kind: "money" }),
    entry("c", { kind: "physical" }),
  ]), ABBR);
  assert.deepEqual(tiersIn(html), ["1", "3", "other"]);
  assert(html.includes("1. Life and health (1)"));
  assert(html.includes("3. Money (1)"));
  assert(html.includes("Other harms (1)"));
  assert(!html.includes("2. Money harm that puts life or health at risk"));
});

test("livelihood defaults to tier 2 with its verbatim label", () => {
  const html = api.buildHarmsListHtml(trackersWith([entry("a", { kind: "livelihood" })]), ABBR);
  assert.deepEqual(tiersIn(html), ["2"]);
  assert(html.includes("2. Money harm that puts life or health at risk (1)"));
});

test("glance.harm.tier overrides the kind's default", () => {
  const html = api.buildHarmsListHtml(trackersWith([
    entry("promoted", { kind: "rights", tier: 1 }),
    entry("plain", { kind: "rights" }),
  ]), ABBR);
  assert.deepEqual(tiersIn(html), ["1", "other"]);
  assert(section(html, 'data-tier="1"').includes('data-id="promoted"'));
  assert(!section(html, 'data-tier="other"').includes('data-id="promoted"'));
});

test("Other harms holds rights, environment, institutional sub-groups in order with counts", () => {
  const html = api.buildHarmsListHtml(trackersWith([
    entry("a", { kind: "institutional" }),
    entry("b", { kind: "environment" }),
    entry("c", { kind: "rights" }),
    entry("d", { kind: "rights" }),
  ]), ABBR);
  const kinds = [...html.matchAll(/data-kind="([a-z]+)"/g)].map(m => m[1]);
  assert.deepEqual(kinds, ["rights", "environment", "institutional"]);
  assert(html.includes("Rights &amp; liberty (2)"));
  assert(html.includes("Environment (1)"));
  assert(html.includes("Institutional integrity (1)"));
  assert(html.includes("Other harms (4)"));
});

test("lines sort by certainty (documented, projected, alleged, averted), then A-Z", () => {
  const html = api.buildHarmsListHtml(trackersWith([
    entry("v", { kind: "physical", certainty: "averted", who: "aaa" }),
    entry("l", { kind: "physical", certainty: "alleged", who: "aaa" }),
    entry("d2", { kind: "physical", certainty: "documented", who: "zzz" }),
    entry("p", { kind: "physical", certainty: "projected", who: "aaa" }),
    entry("d1", { kind: "physical", certainty: "documented", who: "bbb" }),
  ]), ABBR);
  const ids = [...html.matchAll(/data-id="([^"]+)"/g)].map(m => m[1]);
  assert.deepEqual(ids, ["d1", "d2", "p", "l", "v"]);
});

test("each line carries an explained certainty tag; no certainty sub-headings remain", () => {
  const html = api.buildHarmsListHtml(trackersWith([
    entry("a", { certainty: "documented" }),
    entry("b", { certainty: "projected" }),
    entry("c", { certainty: "alleged" }),
    entry("d", { certainty: "averted" }),
  ]), ABBR);
  assert(html.includes('<span class="harm-cert harm-cert-documented" title="On the record (official record, court finding or admission)">Documented</span>'));
  assert(html.includes('<span class="harm-cert harm-cert-projected" title="The action happened; the harm is expected">Projected</span>'));
  assert(html.includes('<span class="harm-cert harm-cert-alleged" title="Claimed by critics and disputed, or no official record">Alleged</span>'));
  assert(html.includes('<span class="harm-cert harm-cert-averted" title="Blocked or withdrawn before it took effect">Averted</span>'));
  assert(!html.includes("harms-cert-label"));
  assert(!html.includes("Documented ("));
});

test("the key explains all four certainty values, verbatim", () => {
  const html = api.buildHarmsListHtml(trackersWith([entry("a", {})]), ABBR);
  const key = html.match(/<dl class="harms-key">([\s\S]*?)<\/dl>/);
  assert(key, "key present");
  for (const [term, text] of [
    ["Documented", "on the record (official record, court finding or admission)"],
    ["Projected", "the action happened; the harm is expected"],
    ["Alleged", "claimed by critics and disputed, or no official record"],
    ["Averted", "blocked or withdrawn before it took effect"],
  ]) {
    assert(key[1].includes("<dt>" + term + "</dt><dd>" + escapeForTest(text) + "</dd>"), term);
  }
});
function escapeForTest(s) { return s.replace(/&/g, "&amp;"); }

test("title reads Harms (Joe, 2026-11-19)", () => {
  const html = api.buildHarmsListHtml(trackersWith([]), ABBR);
  assert(html.includes('<h2 class="harms-title">Harms</h2>'));
});

test("each line links to its entry and shows the what line and a tracker-name button", () => {
  const NAMES = { prosecution: "Cabinet-Level Officials" };
  const html = api.buildHarmsListHtml(trackersWith([entry("e1", {}, "Jailed people without hearings")]), ABBR, NAMES);
  assert(html.includes('<a href="#prosecution/e1" class="harm-entry-link" data-tracker-key="prosecution" data-id="e1">Example detainees</a>'));
  assert.match(html, /<span class="harm-what">[^<]*Jailed people without hearings<\/span>/);
  // Tracker tag (2026-11-22): a button with the full name, short code for phones.
  assert(html.includes('<button type="button" class="entry-row-tracker harm-tracker" data-goto-tracker="prosecution" title="Open Cabinet-Level Officials">'));
  assert(html.includes('<span class="tracker-name-medium">Cabinet-Level Officials</span><span class="tracker-name-abbr">CLA</span>'));
});

test("the status tag leads the row, before the tracker tag and the text", () => {
  const html = api.buildHarmsListHtml(trackersWith([entry("e1", {})]), ABBR);
  const row = html.match(/<li class="harm-row"[^>]*>(.*?)<\/li>/)[1];
  assert(row.indexOf("harm-cert") < row.indexOf("harm-tracker"));
  assert(row.indexOf("harm-tracker") < row.indexOf("harm-entry-link"));
});

test("total keeps its certainty breakdown and leaves averted out of the headline number", () => {
  const html = api.buildHarmsListHtml(trackersWith([
    entry("a", {}), entry("b", {}), entry("c", { certainty: "alleged" }), entry("d", { certainty: "averted" }),
  ]), ABBR);
  const total = html.match(/<p class="harms-total">([^<]*)<\/p>/);
  assert(total, "total line present");
  assert.match(total[1], /^3 harms: 2 documented, 1 alleged; plus 1 averted$/);
});

test("escapes HTML in who, what and id", () => {
  const html = api.buildHarmsListHtml(trackersWith([entry('id"1', { who: 'A<b>&"' }, "x<script>")]), ABBR);
  assert(!html.includes("<b>"));
  assert(!html.includes("<script>"));
  assert(html.includes('href="#prosecution/id%221"'));
  assert(html.includes('data-id="id&quot;1"'));
  assert(html.includes("A&lt;b&gt;&amp;&quot;"));
});

test("averted lines carry the muted class", () => {
  const html = api.buildHarmsListHtml(trackersWith([entry("a", { certainty: "averted" }), entry("b", {})]), ABBR);
  assert.match(html, /<li class="harm-row harm-line-averted"[^>]*>(?:(?!<\/li>).)*data-id="a"/);
  assert.match(html, /<li class="harm-row"[^>]*>(?:(?!<\/li>).)*data-id="b"/);
});

test("an empty input renders the heading, key and a zero total, no tier sections", () => {
  const html = api.buildHarmsListHtml(trackersWith([]), ABBR);
  assert(html.startsWith('<section class="harms-list">'));
  assert(!html.includes("harms-tier"));
  assert.match(html, /<p class="harms-total">0 harms<\/p>/);
});

// #harms address (Task 2): when to open, set or clear it.
const { harmsHashAction } = (0, eval)(`${extractFunction(source, "harms-hash")}\n({ harmsHashAction });`);

test("harmsHashAction opens the view on load only for #harms", () => {
  assert.equal(harmsHashAction("#harms", "headlines", "load"), "open");
  assert.equal(harmsHashAction("#prosecution/x", "headlines", "load"), null);
  assert.equal(harmsHashAction("", "headlines", "load"), null);
});

test("harmsHashAction sets #harms on entering the view and clears it on leaving", () => {
  assert.equal(harmsHashAction("", "harms", "switch"), "set");
  assert.equal(harmsHashAction("#harms", "prosecution", "switch"), "clear");
  assert.equal(harmsHashAction("#harms", "harms", "switch"), null);
  assert.equal(harmsHashAction("#owner-setup", "prosecution", "switch"), null);
  assert.equal(harmsHashAction("#prosecution/x", "prosecution", "switch"), null);
});

// Final-review fixes: history handling (Back from an entry returns to Harms;
// the #harms sync keeps whatever state the current history entry carries).
const hist = (0, eval)(`${extractFunction(source, "harms-hash")}\n({ harmsHashReplacement, harmsLinkHistory });`);

test("harmsHashReplacement keeps the current history state when setting or clearing #harms", () => {
  const st = { type: "entry", tracker: "prosecution", id: "x" };
  assert.deepEqual(hist.harmsHashReplacement("#harms", "prosecution", st, "/tap/", true), { state: st, url: "/tap/" });
  assert.deepEqual(hist.harmsHashReplacement("", "harms", st, "/tap/", true), { state: st, url: "#harms" });
  assert.equal(hist.harmsHashReplacement("#harms", "harms", st, "/tap/", true), null);
});

test("harmsLinkHistory stamps a harms return point, then pushes the entry", () => {
  assert.deepEqual(hist.harmsLinkHistory("govservices", "g1", 1234), [
    { op: "replace", state: { type: "harms", scrollY: 1234 }, url: "#harms" },
    { op: "push", state: { type: "entry", tracker: "govservices", id: "g1" }, url: "#harms" },
  ]);
});

// Minor fixes (2026-11-16, Joe): the headline total leaves averted out.
test("total leaves averted out of the headline and lists it after", () => {
  const html = api.buildHarmsListHtml(trackersWith([
    entry("a", {}), entry("b", { certainty: "alleged" }), entry("c", { certainty: "averted" }),
  ]), ABBR);
  const total = html.match(/<p class="harms-total">([^<]*)<\/p>/)[1];
  assert.equal(total, "2 harms: 1 documented, 1 alleged; plus 1 averted");
});

test("total with no averted has no averted clause", () => {
  const html = api.buildHarmsListHtml(trackersWith([entry("a", {})]), ABBR);
  assert.equal(html.match(/<p class="harms-total">([^<]*)<\/p>/)[1], "1 harm: 1 documented");
});

test("harmsHashReplacement does nothing until the data has loaded", () => {
  assert.equal(hist.harmsHashReplacement("#harms", "headlines", null, "/tap/", false), null);
  assert.deepEqual(hist.harmsHashReplacement("#harms", "headlines", null, "/tap/", true), { state: null, url: "/tap/" });
});

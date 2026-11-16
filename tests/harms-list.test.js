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
  assert.deepEqual(p1, { key: "prosecution", id: "p1", kind: "rights", certainty: "documented", who: "Example detainees", what: "Did an example thing" });
});

test("kinds render in severity order and empty kinds are omitted", () => {
  const html = api.buildHarmsListHtml(trackersWith([
    entry("a", { kind: "institutional" }),
    entry("b", { kind: "rights" }),
    entry("c", { kind: "physical" }),
  ]), ABBR);
  const kinds = [...html.matchAll(/data-kind="([a-z]+)"/g)].map(m => m[1]);
  assert.deepEqual(kinds, ["physical", "rights", "institutional"]);
  assert(!html.includes('data-kind="money"'));
});

test("certainty sub-groups render documented, projected, alleged, averted and empty ones are omitted", () => {
  const html = api.buildHarmsListHtml(trackersWith([
    entry("a", { certainty: "averted" }),
    entry("b", { certainty: "alleged" }),
    entry("c", { certainty: "documented" }),
  ]), ABBR);
  const certs = [...html.matchAll(/class="harms-cert harms-cert-([a-z]+)"/g)].map(m => m[1]);
  assert.deepEqual(certs, ["documented", "alleged", "averted"]);
  assert(!html.includes("harms-cert-projected"));
});

test("lines sort alphabetically by harm.who, case-insensitive, ties by id", () => {
  const html = api.buildHarmsListHtml(trackersWith([
    entry("z", { who: "cherry" }),
    entry("y2", { who: "Banana" }),
    entry("y1", { who: "banana" }),
    entry("x", { who: "apple" }),
  ]), ABBR);
  const ids = [...html.matchAll(/data-id="([^"]+)"/g)].map(m => m[1]);
  assert.deepEqual(ids, ["x", "y1", "y2", "z"]);
});

test("each line links to its entry and shows the what line and tracker abbreviation", () => {
  const html = api.buildHarmsListHtml(trackersWith([entry("e1", {}, "Jailed people without hearings")]), ABBR);
  assert(html.includes('<a href="#prosecution/e1" class="harm-entry-link" data-tracker-key="prosecution" data-id="e1">Example detainees</a>'));
  assert.match(html, /<span class="harm-what">[^<]*Jailed people without hearings<\/span>/);
  assert.match(html, /<span class="harm-tracker">CLA<\/span>/);
});

test("counts: kind heading, certainty heading, and total with breakdown", () => {
  const html = api.buildHarmsListHtml(trackersWith([
    entry("a", {}), entry("b", {}), entry("c", { certainty: "alleged" }),
  ]), ABBR);
  assert(html.includes("Rights &amp; liberty (3)"));
  assert(html.includes("Documented (2)"));
  assert(html.includes("Alleged (1)"));
  const total = html.match(/<p class="harms-total">([^<]*)<\/p>/);
  assert(total, "total line present");
  assert.match(total[1], /3 harms/);
  assert.match(total[1], /2 documented/);
  assert.match(total[1], /1 alleged/);
  assert(!/projected/.test(total[1]), "zero parts are left out of the breakdown");
});

test("escapes HTML in who, what and id", () => {
  const html = api.buildHarmsListHtml(trackersWith([entry('id"1', { who: 'A<b>&"' }, "x<script>")]), ABBR);
  assert(!html.includes("<b>"));
  assert(!html.includes("<script>"));
  assert(html.includes('href="#prosecution/id%221"'));
  assert(html.includes('data-id="id&quot;1"'));
  assert(html.includes("A&lt;b&gt;&amp;&quot;"));
});

test("averted block carries the muted class", () => {
  const html = api.buildHarmsListHtml(trackersWith([entry("a", { certainty: "averted" })]), ABBR);
  const start = html.indexOf('harms-cert-averted"');
  assert(start !== -1);
  assert(html.indexOf('data-id="a"', start) > start);
});

test("an empty input renders the heading and a zero total, no kind sections", () => {
  const html = api.buildHarmsListHtml(trackersWith([]), ABBR);
  assert(html.startsWith('<section class="harms-list">'));
  assert(!html.includes("harms-kind"));
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
  assert.deepEqual(hist.harmsHashReplacement("#harms", "prosecution", st, "/tap/"), { state: st, url: "/tap/" });
  assert.deepEqual(hist.harmsHashReplacement("", "harms", st, "/tap/"), { state: st, url: "#harms" });
  assert.equal(hist.harmsHashReplacement("#harms", "harms", st, "/tap/"), null);
});

test("harmsLinkHistory stamps a harms return point, then pushes the entry", () => {
  assert.deepEqual(hist.harmsLinkHistory("govservices", "g1", 1234), [
    { op: "replace", state: { type: "harms", scrollY: 1234 }, url: "#harms" },
    { op: "push", state: { type: "entry", tracker: "govservices", id: "g1" }, url: "#harms" },
  ]);
});

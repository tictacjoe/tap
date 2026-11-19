// Possible Illegality view (2026-11-19): pure row/sort/filter/HTML/hash functions.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function extractFunction(source, name) {
  const s = `/* ${name}:start */`, e = `/* ${name}:end */`;
  const a = source.indexOf(s), b = source.indexOf(e);
  if (a === -1 || b === -1) throw new Error(`Markers for ${name} not found in index.html`);
  return source.slice(a + s.length, b);
}

const source = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");
const combined = ["escape-html", "highlight-matches", "matches-term", "visible-tracker-keys", "harms-list", "illegality-view"]
  .map(n => extractFunction(source, n)).join("\n");
const api = (0, eval)(`${combined}
({ buildIllegalityRows, actionSortDate, sortIllegalityRows, filterIllegalityRows, illegalityCounts,
   buildIllegalityHtml, illegalityHashAction, illegalityLinkHistory, ILLEGALITY_SORTS });`);

const LAWS = {
  bribery: { name: "Bribery", cite: "18 U.S.C. 201", label: "criminal" },
  ica: { name: "Impoundment Control Act", label: "civil" },
  apa: { name: "Administrative Procedure Act", cite: "5 U.S.C. 706", label: "civil" },
};
function ent(id, what, over = {}) {
  return { id, status_stage: "Unchallenged", date_of_action: "2025-03-01", last_substantive_update: "2026-01-01",
    glance: { what, harm: { kind: "money" } }, ...over };
}
function trackers(extra = {}) {
  return {
    govservices: { idField: "id", data: [ent("g1", "Zeta", { glance: { what: "Zeta", harm: { kind: "physical" } } }), ent("g2", "Alpha")] },
    dai: { idField: "id", data: [ent("d1", "Moved one")] },
    tracker: { idField: "id", data: [ent("r1", "Reporting")] },
    prosecution: { idField: "id", hidden: true, data: [ent("h1", "Hidden")] },
    ...extra,
  };
}
const V = (law, who = "Agency", why = "Why.") => ({ law, who, why });
function data(entries) {
  return { version: 1, laws: LAWS, entries, progress: { screened: 3, total: 940 } };
}
const rowsFor = e => api.buildIllegalityRows(trackers(), data(e));

test("two-label row: one row, counts once in total, once per split, sorts as criminal", () => {
  const rows = rowsFor({ g1: [V("bribery"), V("ica")], g2: [V("ica")], d1: [V("apa")] });
  const two = rows.find(r => r.id === "g1");
  assert.deepEqual(two.labels, ["civil", "criminal"]);
  assert.deepEqual(api.illegalityCounts(rows), { total: 3, criminal: 1, civil: 3, unchallenged: 3 });
  const sorted = api.sortIllegalityRows(rows, "label");
  assert.equal(sorted[0].id, "g1");
});

test("moved entry: id held by dai yields key dai", () => {
  const rows = rowsFor({ d1: [V("ica")] });
  assert.equal(rows[0].key, "dai");
  assert.equal(rows[0].what, "Moved one");
});

test("id not in TRACKERS (or hidden / Reporting) skipped", () => {
  const rows = rowsFor({ nope: [V("ica")], h1: [V("ica")], r1: [V("ica")], g2: [V("ica")] });
  assert.deepEqual(rows.map(r => r.id), ["g2"]);
});

test("row fields", () => {
  const r = rowsFor({ g1: [V("bribery", "Sec. X", "Because.")] })[0];
  assert.equal(r.harmTier, 1);
  assert.equal(r.status, "Unchallenged");
  assert.equal(r.actionDate, "2025-03-01");
  assert.equal(r.updated, "2026-01-01");
  assert.deepEqual(r.violations[0], { law: "bribery", name: "Bribery", cite: "18 U.S.C. 201", label: "criminal", who: "Sec. X", why: "Because." });
});

test("actionSortDate", () => {
  assert.equal(api.actionSortDate("2025-03-01"), "2025-03-01");
  assert.equal(api.actionSortDate("early 2025 ... through 2026-10-15"), "2025-00-00");
  assert.equal(api.actionSortDate("2025-08 (x) through 2026-06-26"), "2025-08-00");
  assert.equal(api.actionSortDate("Ongoing since early 2025"), "2025-00-00");
  assert.equal(api.actionSortDate(null), null);
  assert.equal(api.actionSortDate("unknown"), null);
});

test("null action dates sort last, newest first", () => {
  const t = trackers();
  t.govservices.data = [ent("a", "A", { date_of_action: null }), ent("b", "B", { date_of_action: "2024-01-01" }), ent("c", "C", { date_of_action: "2026-02-02" })];
  const rows = api.buildIllegalityRows(t, data({ a: [V("ica")], b: [V("ica")], c: [V("ica")] }));
  assert.deepEqual(api.sortIllegalityRows(rows, "action").map(r => r.id), ["c", "b", "a"]);
});

function mk(id, status, tier, what, extra = {}) {
  return { id, key: "govservices", what, status, harmTier: tier, actionDate: null, updated: null,
    violations: [{ law: "ica", name: "ICA", label: "civil", who: "W", why: "y" }], labels: ["civil"], ...extra };
}

test("default order: status, harm tier (null last), what, id", () => {
  const rows = [
    mk("1", "In court", 1, "A"), mk("2", "Unchallenged", null, "A"), mk("3", "Unchallenged", 2, "B"),
    mk("4", "Unchallenged", 2, "A"), mk("5", "Reversed or withdrawn", 1, "A"), mk("7", "Unchallenged", 2, "A"),
  ];
  assert.deepEqual(api.sortIllegalityRows(rows, "status").map(r => r.id), ["4", "7", "3", "2", "1", "5"]);
});

test("each sort ties to the default", () => {
  const rows = [
    mk("b", "In court", 2, "B", { actionDate: "2025-01-01", updated: "2026-01-01" }),
    mk("a", "Unchallenged", 3, "A", { actionDate: "2025-01-01", updated: "2026-01-01" }),
    mk("c", "Unchallenged", 1, "Z", { actionDate: "2025-01-01", updated: "2026-01-01" }),
  ];
  for (const [k] of api.ILLEGALITY_SORTS) {
    // all rows tie on label/law/who/tracker/date, so each sort must equal the default order
    if (["harm", "status"].includes(k)) continue;
    assert.deepEqual(api.sortIllegalityRows(rows, k).map(r => r.id), ["c", "a", "b"], k);
  }
  assert.deepEqual(api.sortIllegalityRows(rows, "harm").map(r => r.id), ["c", "b", "a"]);
});

test("law and who sorts use the first violation", () => {
  const a = mk("a", "Unchallenged", 1, "A", { violations: [{ name: "Zed", who: "Yan" }, { name: "Abe", who: "Abe" }] });
  const b = mk("b", "Unchallenged", 1, "B", { violations: [{ name: "Mid", who: "Mid" }] });
  assert.deepEqual(api.sortIllegalityRows([a, b], "law").map(r => r.id), ["b", "a"]);
  assert.deepEqual(api.sortIllegalityRows([a, b], "who").map(r => r.id), ["b", "a"]);
});

test("filters and search", () => {
  const rows = rowsFor({ g1: [V("bribery", "Sec. Smith", "Took gifts")], g2: [V("ica")], d1: [V("apa")] });
  const f = o => api.filterIllegalityRows(rows, o).map(r => r.id).sort();
  assert.deepEqual(f({}), ["d1", "g1", "g2"]);
  assert.deepEqual(f({ label: "criminal" }), ["g1"]);
  assert.deepEqual(f({ tracker: "dai" }), ["d1"]);
  assert.deepEqual(f({ law: "ica" }), ["g2"]);
  assert.deepEqual(f({ status: "Unchallenged" }), ["d1", "g1", "g2"]);
  assert.deepEqual(f({ term: "smith" }), ["g1"]);
  assert.deepEqual(f({ term: "706" }), ["d1"]);
  assert.deepEqual(f({ term: "^Moved", regex: true }), ["d1"]);
});

test("empty rows: progress shown and None listed yet.", () => {
  const html = api.buildIllegalityHtml([], { total: 0, criminal: 0, civil: 0 }, { screened: 0, total: 940 }, {}, {});
  assert.match(html, /Reviewed so far: 0 of 940 entries/);
  assert.match(html, /None listed yet\./);
});

test("rows exist but filtered out: No entries match.", () => {
  const html = api.buildIllegalityHtml([], { total: 5, criminal: 1, civil: 4 }, { screened: 5, total: 940 }, {}, {});
  assert.match(html, /No entries match\./);
});

test("html: row content, escaping, selected control values", () => {
  const rows = rowsFor({ g1: [V("bribery", "<b>Who</b>", "Why & so")] });
  const counts = api.illegalityCounts(rows);
  const html = api.buildIllegalityHtml(rows, counts, { screened: 1, total: 940 }, { govservices: "GSR" }, {
    label: "criminal", status: "", tracker: "govservices", law: "", sort: "who", term: "a\"b",
    laws: [["bribery", "Bribery"]], trackers: [["govservices", "GSR"]] });
  assert.match(html, /1 (entry|entries) · 1 criminal · 0 civil\/constitutional · 1 unchallenged/);
  assert.match(html, /class="ill-results" aria-live="polite"/);
  assert.match(html, /class="ill-entry-link"[^>]*data-tracker-key="govservices"[^>]*data-id="g1"|data-tracker-key="govservices"/);
  assert.match(html, /Bribery \(18 U\.S\.C\. 201\)/);
  assert.match(html, /Who:/);
  assert.match(html, /&lt;b&gt;Who&lt;\/b&gt;/);
  assert.ok(!html.includes("<b>Who</b>"));
  assert.match(html, /id="ill-label"/);
  assert.match(html, /<option value="criminal" selected>/);
  assert.match(html, /<option value="who" selected>/);
  assert.match(html, /id="ill-search"[^>]*value="a&quot;b"/);
  for (const id of ["ill-status", "ill-tracker", "ill-law", "ill-sort"]) assert.ok(html.includes(`id="${id}"`), id);
  assert.match(html, /GSR/);
});

test("hash action mirrors harms", () => {
  assert.equal(api.illegalityHashAction("#illegality", "headlines", "load"), "open");
  assert.equal(api.illegalityHashAction("#harms", "headlines", "load"), null);
  assert.equal(api.illegalityHashAction("", "illegality", "switch"), "set");
  assert.equal(api.illegalityHashAction("#illegality", "prosecution", "switch"), "clear");
  assert.equal(api.illegalityHashAction("#illegality", "illegality", "switch"), null);
  assert.equal(api.illegalityHashAction("#owner-setup", "prosecution", "switch"), null);
});

test("link history", () => {
  assert.deepEqual(api.illegalityLinkHistory("dai", "d1", 120), [
    { op: "replace", state: { type: "illegality", scrollY: 120 }, url: "#illegality" },
    { op: "push", state: { type: "entry", tracker: "dai", id: "d1" }, url: "#illegality" },
  ]);
});

test("counts: unchallenged is rows whose status is Unchallenged", () => {
  const rows = rowsFor({ g1: [V("bribery")], g2: [V("ica")] });
  rows[1].status = "In court";
  assert.deepEqual(api.illegalityCounts(rows), { total: 2, criminal: 1, civil: 1, unchallenged: 1 });
});

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
const names = ["escape-html", "visible-tracker-keys", "map-trumpfamily-entry",
               "build-trumpfamily-card-html", "family-group-keys",
               "resolve-entry-target", "global-search-database-count", "tfs-count-for-official"];
const fns = (0, eval)(names.map(n => extractFunction(source, n)).join("\n") +
  "\n({ visibleTrackerKeys, mapTrumpFamilyEntry, buildTrumpFamilyCardHtml, familyGroupKeys,\n" +
  "   resolveEntryTarget, globalSearchDatabaseCount, tfsCountForOfficial });");

const RAW = {
  id: "wlf-uae", title: "UAE fund buys into WLF", category: "crypto",
  family_members: ["Eric Trump", "Donald Trump Jr."],
  business_entity: { name: "World Liberty Financial", family_stake: "40% family stake" },
  government_nexus: { action: "Chip export approval", official: { name: "Steve Witkoff", role: "Special Envoy" }, note: "Approval followed the deal." },
  financial_stake: { summary: "$2B investment", figures: [{ metric: "Investment", value: "$2 billion", source: "Reuters" }], caveat: "White House denies a link." },
  legal_context: "Foreign Emoluments Clause",
  section_summaries: { what_changed: "s1", financial_stake: "s2" },
};

test("visibleTrackerKeys drops hidden trackers, keeps order", () => {
  assert.deepEqual(fns.visibleTrackerKeys({ a: {}, b: { hidden: true }, c: { hidden: false } }), ["a", "c"]);
});

test("mapTrumpFamilyEntry fills the GSR shape and keeps TFS fields", () => {
  const m = fns.mapTrumpFamilyEntry(RAW);
  assert.equal(m.domain, "crypto");
  assert.equal(m.institution, "World Liberty Financial");
  assert.deepEqual(m.primary_proponent, { name: "Steve Witkoff", role: "Special Envoy", note: "Approval followed the deal." });
  assert.equal(m.estimated_impact.figures[0].value, "$2 billion");
  assert.equal(m.section_summaries.estimated_impact, "s2");
  assert.equal(m.section_summaries.what_changed, "s1");
  assert.deepEqual(m.family_members, RAW.family_members);
  assert.equal(RAW.domain, undefined, "input not mutated");
});

test("mapTrumpFamilyEntry tolerates missing nested objects", () => {
  const m = fns.mapTrumpFamilyEntry({ id: "x", title: "X" });
  assert.equal(m.institution, "");
  assert.equal(m.primary_proponent.name, "");
  assert.deepEqual(m.estimated_impact, {});
});

test("buildTrumpFamilyCardHtml shows members, stake, action and labeled legal context, escaped", () => {
  const hl = t => String(t || "").replace(/&/g, "&amp;").replace(/</g, "&lt;");
  const html = fns.buildTrumpFamilyCardHtml(Object.assign({}, RAW, { family_members: ["Eric <b>Trump</b>"] }), hl);
  assert.match(html, /Eric &lt;b>Trump/);
  assert.match(html, /40% family stake/);
  assert.match(html, /Chip export approval/);
  assert.match(html, /Legal context \(not a finding\)/);
  assert.doesNotMatch(fns.buildTrumpFamilyCardHtml(Object.assign({}, RAW, { legal_context: undefined }), hl), /Legal context/);
});

test("familyGroupKeys returns every member, with a fallback", () => {
  assert.deepEqual(fns.familyGroupKeys(RAW), ["Eric Trump", "Donald Trump Jr."]);
  assert.deepEqual(fns.familyGroupKeys({}), ["Unnamed"]);
});

// visibleSearchText: TFS's own visible fields are in the haystack; a GSR
// entry's haystack ignores them (they only exist on TFS entries).
const searchApi = (0, eval)(["escape-html", "highlight-matches", "glance-head", "visible-search-text"]
  .map(n => extractFunction(source, n)).join("\n") + "\n({ visibleSearchText });");
const TFS_CFG = { kind: "govservices", titleField: "title", trackerKey: "trumpfamily", glanceEnabled: true };
const GSR_CFG = { kind: "govservices", titleField: "title", trackerKey: "govservices", glanceEnabled: true };

test("visibleSearchText covers TFS family, stake, action and legal context", () => {
  const text = searchApi.visibleSearchText(fns.mapTrumpFamilyEntry(RAW), TFS_CFG);
  for (const needle of ["Donald Trump Jr.", "Eric Trump", "40% family stake", "Chip export approval", "Emoluments"]) {
    assert.ok(text.includes(needle), needle);
  }
});

test("visibleSearchText for a GSR entry is unchanged by the TFS fields", () => {
  const gsr = { title: "SNAP freeze", institution: "USDA", domain: "food", what_changed: "Benefits paused." };
  const base = searchApi.visibleSearchText(gsr, GSR_CFG);
  const withTfsFields = searchApi.visibleSearchText(Object.assign({}, gsr, {
    family_members: RAW.family_members, business_entity: RAW.business_entity,
    government_nexus: RAW.government_nexus, legal_context: RAW.legal_context,
  }), GSR_CFG);
  assert.equal(withTfsFields, base);
  assert.equal(base, "SNAP freeze \n USDA \n food \n Benefits paused.");
});

// --- Phase B (Task 6): old-link redirects, database count, CLA also-in-TFS ---
const TRK = {
  prosecution: { idField: "id", data: [{ id: "cla1" }] },
  trumpfamily: { idField: "id", data: [{ id: "m1" }] },
  hiddenone: { idField: "id", hidden: true, data: [{ id: "h1" }] },
};
const MOVED = { m1: { from: "prosecution", to: "trumpfamily", date: "2026-10-20" },
                h1: { from: "prosecution", to: "hiddenone", date: "2026-10-20" } };

test("resolveEntryTarget: normal link unchanged, no rewrite", () => {
  assert.deepEqual(fns.resolveEntryTarget("prosecution", "cla1", TRK, MOVED), { key: "prosecution", id: "cla1", moved: false });
});
test("resolveEntryTarget: moved id redirects to its new tracker", () => {
  assert.deepEqual(fns.resolveEntryTarget("prosecution", "m1", TRK, MOVED), { key: "trumpfamily", id: "m1", moved: true });
});
test("resolveEntryTarget: move into a hidden tracker does not redirect", () => {
  assert.deepEqual(fns.resolveEntryTarget("prosecution", "h1", TRK, MOVED), { key: "prosecution", id: "h1", moved: false });
});
test("resolveEntryTarget: unknown id on a visible tracker keeps today's behavior; hidden or missing tracker -> null", () => {
  assert.deepEqual(fns.resolveEntryTarget("prosecution", "zzz", TRK, MOVED), { key: "prosecution", id: "zzz", moved: false });
  assert.equal(fns.resolveEntryTarget("hiddenone", "h1", TRK, MOVED), null);
  assert.equal(fns.resolveEntryTarget("nope", "x", TRK, MOVED), null);
  assert.deepEqual(fns.resolveEntryTarget("prosecution", "m1", TRK, {}), { key: "prosecution", id: "m1", moved: false });
});
test("globalSearchDatabaseCount counts visible non-Reporting trackers", () => {
  assert.equal(fns.globalSearchDatabaseCount({ a: {}, b: { hidden: true }, tracker: {}, c: {} }), 2);
});
test("tfsCountForOfficial matches the name before the first comma", () => {
  const tfs = [{ government_nexus: { official: { name: "Steve Witkoff" } } },
               { government_nexus: { official: { name: "Steve Witkoff" } } },
               { government_nexus: { official: { name: "Pete Hegseth" } } }, {}];
  assert.equal(fns.tfsCountForOfficial("Steve Witkoff", tfs), 2);
  assert.equal(fns.tfsCountForOfficial("Kristi Noem", tfs), 0);
});

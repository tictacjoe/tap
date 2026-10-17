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
               "build-trumpfamily-card-html", "family-group-keys"];
const fns = (0, eval)(names.map(n => extractFunction(source, n)).join("\n") +
  "\n({ visibleTrackerKeys, mapTrumpFamilyEntry, buildTrumpFamilyCardHtml, familyGroupKeys });");

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

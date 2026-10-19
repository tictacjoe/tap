// DHS and ICE (DAI) site functions. Spec: tap-data
// docs/superpowers/specs/2026-10-18-tap-dai-tracker-design.md sec-7.
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
const fns = (0, eval)(["escape-html", "map-dai-entry", "build-dai-people-html", "dai-group-keys", "cross-view-officials"]
  .map(n => extractFunction(source, n)).join("\n") +
  "\n({ mapDaiEntry, buildDaiPeopleHtml, daiAgencyGroupKeys, daiOfficialGroupKeys,\n" +
  "   crossViewOfficialNames, crossViewCount, crossViewOnlyOfficials, CROSS_VIEW_TRACKERS });");

const RAW = {
  id: "broadview-fx", title: "Fixture shooting", category: "use_of_force",
  agencies: ["Border Patrol", "ICE"], location: { place: "Broadview, Illinois" },
  people: {
    officials: [{ name: "Greg Bovino", role: "Border Patrol commander", sources: ["https://a.example/1"] }],
    agents: [{ name: "Agent Fixture", role: "Border Patrol agent", incident_role: "fired the shots", sources: ["https://a.example/1", "https://b.example/2"] }],
    affected: [{ name: "Person Fixture", description: "U.S. citizen shot", sources: ["https://b.example/2"] }],
    unnamed_affected: "a bystander",
  },
  legal_status: "Under investigation by the state attorney general",
  human_toll: { summary: "One person shot", figures: [{ metric: "Shot", value: "1", source: "AP" }], caveat: "DHS says the agent was assaulted." },
  section_summaries: { what_changed: "s1", human_toll: "s2" },
};
const hl = t => String(t || "").replace(/&/g, "&amp;").replace(/</g, "&lt;");

test("mapDaiEntry fills the GSR shape and keeps DAI fields", () => {
  const m = fns.mapDaiEntry(RAW);
  assert.equal(m.domain, "use_of_force");
  assert.equal(m.institution, "Border Patrol, ICE");
  assert.deepEqual(m.primary_proponent, { name: "Greg Bovino", role: "Border Patrol commander" });
  assert.equal(m.estimated_impact, RAW.human_toll);
  assert.equal(m.section_summaries.estimated_impact, "s2");
  assert.equal(m.section_summaries.what_changed, "s1");
  assert.deepEqual(m.people, RAW.people);
  assert.equal(RAW.domain, undefined, "input not mutated");
});

test("mapDaiEntry tolerates empty officials and a missing people block", () => {
  const empty = fns.mapDaiEntry(Object.assign({}, RAW, { people: { officials: [] } }));
  assert.equal(empty.primary_proponent.name, "");
  const bare = fns.mapDaiEntry({ id: "x", title: "X" });
  assert.equal(bare.institution, "");
  assert.equal(bare.primary_proponent.name, "");
  assert.deepEqual(bare.estimated_impact, {});
});

test("buildDaiPeopleHtml shows the three groups, links each name to its first source, escaped", () => {
  const e = JSON.parse(JSON.stringify(RAW));
  e.people.agents[0].name = "Agent <b>X</b>";
  const html = fns.buildDaiPeopleHtml(e, hl);
  for (const label of ["Officials", "Agents", "Affected"]) assert.match(html, new RegExp(">" + label + "<"));
  assert.match(html, /Agent &lt;b>X/);
  assert.match(html, /<a href="https:\/\/a\.example\/1" target="_blank" rel="noopener">Greg Bovino<\/a>/);
  assert.match(html, /<a href="https:\/\/b\.example\/2" target="_blank" rel="noopener">Person Fixture<\/a>/);
  assert.match(html, /fired the shots/);
  assert.match(html, /a bystander/);
  assert.match(html, /Legal status \(not a finding\)/);
});

test("buildDaiPeopleHtml omits empty groups and an empty legal status", () => {
  const e = { people: { officials: [], agents: [], affected: [] }, legal_status: "" };
  const html = fns.buildDaiPeopleHtml(e, hl);
  assert.doesNotMatch(html, />Officials<|>Agents<|>Affected<|Legal status/);
  assert.doesNotMatch(fns.buildDaiPeopleHtml({}, hl), /Legal status/);
});

test("buildDaiPeopleHtml never links a non-http source", () => {
  const e = { people: { officials: [{ name: "X", sources: ["javascript:alert(1)"] }] } };
  const html = fns.buildDaiPeopleHtml(e, hl);
  assert.doesNotMatch(html, /href/);
  assert.match(html, /X/);
});

test("DAI group keys return agencies / official names, with a fallback", () => {
  assert.deepEqual(fns.daiAgencyGroupKeys(RAW), ["Border Patrol", "ICE"]);
  assert.deepEqual(fns.daiOfficialGroupKeys(RAW), ["Greg Bovino"]);
  assert.deepEqual(fns.daiAgencyGroupKeys({}), ["Unnamed"]);
  assert.deepEqual(fns.daiOfficialGroupKeys({ people: { officials: [] } }), ["Unnamed"]);
});

test("cross-view covers TFS and DAI, in that order", () => {
  assert.deepEqual(fns.CROSS_VIEW_TRACKERS, ["trumpfamily", "dai"]);
});

test("crossViewOfficialNames for DAI reads people.officials, names before the first comma, once each", () => {
  const e = { people: { officials: [{ name: "Greg Bovino" }, { name: "Greg Bovino, commander" }, { name: "" }, {}] } };
  assert.deepEqual(fns.crossViewOfficialNames("dai", e), ["Greg Bovino"]);
  assert.deepEqual(fns.crossViewOfficialNames("dai", {}), []);
  assert.deepEqual(fns.crossViewOfficialNames("nope", e), []);
});

test("crossViewCount and crossViewOnlyOfficials for DAI", () => {
  const dai = [RAW, { people: { officials: [{ name: "Greg Bovino" }, { name: "Kristi Noem" }] } }, {}];
  assert.equal(fns.crossViewCount("dai", "Greg Bovino", dai), 2);
  assert.equal(fns.crossViewCount("dai", "Kristi Noem", dai), 1);
  assert.equal(fns.crossViewCount("dai", "", dai), 0);
  assert.deepEqual(fns.crossViewOnlyOfficials("dai", ["Kristi Noem"], dai), [{ name: "Greg Bovino", count: 2 }]);
  assert.deepEqual(fns.crossViewOnlyOfficials("dai", [], undefined), []);
});

const searchApi = (0, eval)(["escape-html", "highlight-matches", "glance-head", "visible-search-text"]
  .map(n => extractFunction(source, n)).join("\n") + "\n({ visibleSearchText });");
test("visibleSearchText covers DAI agencies, place, people, unnamed and legal status", () => {
  const cfg = { kind: "govservices", titleField: "title", trackerKey: "dai", glanceEnabled: true };
  const text = searchApi.visibleSearchText(fns.mapDaiEntry(RAW), cfg);
  for (const needle of ["Broadview, Illinois", "Greg Bovino", "Agent Fixture", "fired the shots",
                        "Person Fixture", "U.S. citizen shot", "a bystander", "state attorney general"]) {
    assert.ok(text.includes(needle), needle);
  }
});

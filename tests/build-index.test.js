const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { INDEX_FILES, projectEntry, parityProblems } = require("../tools/build_index.js");

const glance = { who: "EPA", what: "Repealed the widget rule.", harm: { kind: "physical", certainty: "documented", who: "Workers" } };
const src = (n) => Array.from({ length: n }, (_, i) => ({ name: "S" + i, url: "https://x/" + i }));
const base = { last_verified: "2026-01-02", date_added: "2026-01-01", last_substantive_update: "2026-01-03", date_of_action: "2025-12-01", status_stage: "Unchallenged", glance };

const cdr = { ...base, id: "cdr-1", rule_name: "Widget rule", domain: "Air", short_summary: "Short.", what_changed: "Long text. More.",
  estimated_health_impact: { summary: "x", figures: [{ metric: "deaths", value: "2,577 mortalities" }] },
  sources: src(3), section_summaries: { what_changed: "One line." }, confidence_note: "HIGH. text" };
const gsr = { ...base, id: "gsr-1", title: "Closed office", domain: "Health", what_changed: "Closed.", estimated_impact: { figures: [{ value: "$300 million" }] },
  sources: src(2), section_summaries: { what_changed: "One line." } };
const tfs = { ...base, id: "tfs-1", title: "Deal", category: "Crypto", family_members: ["Donald Jr."], what_changed: "A deal.",
  government_nexus: { official: { name: "Pat", role: "Sec" }, also_officials: [{ name: "Lee", role: "Dir" }] },
  financial_stake: { figures: [{ value: "$2 billion" }] }, sources: src(1), section_summaries: { what_changed: "One line." } };
const dai = { ...base, id: "dai-1", title: "Death in custody", category: "Deaths", agencies: ["ICE", "DHS"], what_changed: "Died.",
  people: { officials: [{ name: "Kim", role: "Warden" }, { name: "Ray", role: "Agent" }] },
  human_toll: { figures: [{ value: "12 deaths" }] }, sources: src(2), section_summaries: { what_changed: "One line." } };
const cla = { ...base, id: "cla-1", official: "Some Official", offense_category: "Abuse of power; obstruction", contested: true,
  status: "Under investigation by an inspector general", confidence_note: "MODERATE-HIGH. Long text here.",
  incident_summary: "Something happened.", section_summaries: { incident_summary: "One line." },
  evidence: [
    { description: "Re-verified 2026-05-01: still true", source_url: "https://a" },
    { description: "Memo", source_url: "https://b" },
    { description: "Email", source_url: "https://c" },
  ] };
const fixtures = { deregulation: cdr, govservices: gsr, trumpfamily: tfs, dai, prosecution: cla };

test("INDEX_FILES names the five data files", () => {
  assert.deepEqual(INDEX_FILES, {
    prosecution: "prosecution.json", deregulation: "deregulation.json", govservices: "government-services.json",
    trumpfamily: "trumpfamily.json", dai: "dai.json",
  });
});

test("CDR with short_summary drops what_changed and blanks every source", () => {
  const s = projectEntry("deregulation", cdr);
  assert.equal("what_changed" in s, false);
  assert.equal(s.sources.length, cdr.sources.length);
  assert.ok(s.sources.every((x) => Object.keys(x).length === 0));
  assert.deepEqual(s.estimated_health_impact, { figures: [{ value: "2,577 mortalities" }] });
  assert.equal(s.short_summary, "Short.");
});

test("CDR without short_summary or override keeps what_changed whole", () => {
  const { short_summary, ...e } = cdr;
  assert.equal(projectEntry("deregulation", e).what_changed, "Long text. More.");
});

test("CDR with an override headline drops what_changed and keeps only the headline", () => {
  const { short_summary, ...e } = cdr;
  const s = projectEntry("deregulation", { ...e, narrative_override: { headline: "H", full: "long" } });
  assert.equal("what_changed" in s, false);
  assert.deepEqual(s.narrative_override, { headline: "H" });
});

test("a key the full entry lacks is left out, not null", () => {
  const s = projectEntry("govservices", { id: "g", title: "T" });
  assert.deepEqual(s, { id: "g", title: "T" });
});

test("CLA keeps the first token of confidence_note and counts only real evidence", () => {
  const s = projectEntry("prosecution", cla);
  assert.equal(s.confidence_note, "MODERATE-HIGH.");
  assert.equal(s.evidence.length, 2);
  assert.equal("incident_summary" in s, false);
  assert.equal(s.offense_category, cla.offense_category);
  assert.equal(s.status, cla.status);
  assert.deepEqual(s.section_summaries, { incident_summary: "One line." });
});

test("CLA keeps incident_summary when nothing else supplies a headline", () => {
  const { section_summaries, ...e } = cla;
  assert.equal(projectEntry("prosecution", e).incident_summary, "Something happened.");
});

test("TFS and DAI keep only names, roles and figure values", () => {
  const t = projectEntry("trumpfamily", tfs);
  assert.deepEqual(t.government_nexus, { official: { name: "Pat" }, also_officials: [{ name: "Lee" }] });
  assert.deepEqual(t.financial_stake, { figures: [{ value: "$2 billion" }] });
  const d = projectEntry("dai", dai);
  assert.deepEqual(d.people, { officials: [{ name: "Kim", role: "Warden" }, { name: "Ray", role: "Agent" }] });
  assert.deepEqual(d.agencies, ["ICE", "DHS"]);
});

for (const [key, full] of Object.entries(fixtures)) {
  test(`parity: ${key} fixture matches its own projection`, () => {
    assert.deepEqual(parityProblems(key, full, projectEntry(key, full)), []);
  });
}

test("parity flags a changed filter value", () => {
  const slim = { ...projectEntry("govservices", gsr), domain: "X" };
  const problems = parityProblems("govservices", gsr, slim);
  // GSR's Records adapter reads domain as its category, so that check trips too.
  assert.ok(problems.some((p) => p === "gsr-1: filter differs"));
  assert.ok(problems.every((p) => /^gsr-1: /.test(p)));
});

test("parity flags a slim entry that lost its figures (impactScore)", () => {
  const { estimated_impact, ...slim } = projectEntry("govservices", gsr);
  assert.ok(parityProblems("govservices", gsr, slim).some((p) => /impactScore/.test(p)));
});

test("parity flags a wrong CLA confidence tier and a lost group name", () => {
  const slim = { ...projectEntry("prosecution", cla), confidence_note: "LOW." };
  assert.ok(parityProblems("prosecution", cla, slim).some((p) => /impactScore/.test(p)));
  const dslim = { ...projectEntry("dai", dai), people: { officials: [] } };
  assert.ok(parityProblems("dai", dai, dslim).some((p) => /daiOfficialGroupKeys/.test(p)));
});

test("real data: every entry's projection has no parity problems", () => {
  const dataDir = path.join(__dirname, "..", "data");
  for (const [key, file] of Object.entries(INDEX_FILES)) {
    const entries = JSON.parse(fs.readFileSync(path.join(dataDir, file), "utf8"));
    assert.ok(entries.length > 0, `${file} is empty`);
    const problems = entries.flatMap((e) => parityProblems(key, e, projectEntry(key, e)));
    assert.deepEqual(problems, [], `${file}: ${problems.slice(0, 5).join("; ")}`);
  }
});

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

const indexHtmlPath = path.join(__dirname, "..", "index.html");
const source = fs.readFileSync(indexHtmlPath, "utf8");

const names = [
  "truncate",
  "verdict-label",
  "combine-tier-text",
  "usable-tier-count",
  "adapt-deregulation-entry",
  "adapt-govservices-entry",
  "adapt-prosecution-entry",
  "adapt-communitytopic-entry",
  "adapt-reporting-entry",
];
const combined = names.map(n => extractFunction(source, n)).join("\n");
const exposeNames = [
  "combineTierText", "usableTierCount",
  "adaptDeregulationEntry", "adaptGovServicesEntry", "adaptProsecutionEntry",
  "adaptCommunityTopicEntry", "adaptReportingEntry",
];
const fns = (0, eval)(`${combined}\n({ ${exposeNames.join(", ")} });`);

test("combineTierText joins only non-empty parts with a space", () => {
  assert.equal(fns.combineTierText(["a", "", null, "b"]), "a b");
  assert.equal(fns.combineTierText(["", null, undefined]), "");
});

test("usableTierCount counts leading non-empty, non-duplicate tiers", () => {
  assert.equal(fns.usableTierCount(["a", "a b", "a b c"]), 3);
  assert.equal(fns.usableTierCount(["a", "a", "a"]), 1);
  assert.equal(fns.usableTierCount(["a", "a b", "a b"]), 2);
  assert.equal(fns.usableTierCount(["", "x", "y"]), 0);
});

test("adaptDeregulationEntry composes headline/tiers/trail/date/category", () => {
  const entry = {
    short_summary: "Repealed the widget rule.",
    what_changed: "The rule was fully repealed.",
    original_rule_summary: "It required annual widget inspections.",
    estimated_health_impact: { summary: "Raises injury risk." },
    confidence_note: "High confidence.",
    last_verified: "2026-09-01",
    date_of_action: "2026-01-01",
    date_added: "2026-01-15",
    domain: "consumer_safety",
    sources: [{ name: "Agency filing", url: "https://example.com/a" }],
  };
  const r = fns.adaptDeregulationEntry(entry);
  assert.equal(r.headline, "Repealed the widget rule.");
  assert.equal(r.tiers[0], "The rule was fully repealed.");
  assert.match(r.tiers[1], /It required annual widget inspections\./);
  assert.match(r.tiers[2], /Raises injury risk\./);
  assert.equal(r.trail.sources[0].name, "Agency filing");
  assert.equal(r.trail.confidenceNote, "High confidence.");
  assert.equal(r.trail.lastVerified, "2026-09-01");
  assert.equal(r.trail.dateAdded, "2026-01-15");
  assert.equal(r.date, "2026-09-01");
  assert.equal(r.tracker, "deregulation");
  assert.equal(r.category, "consumer_safety");
});

test("adaptDeregulationEntry falls back to truncated what_changed when short_summary missing", () => {
  const r = fns.adaptDeregulationEntry({ what_changed: "x".repeat(200) });
  assert.equal(r.headline.length, 111); // 110 chars + ellipsis
});

test("adaptGovServicesEntry composes headline/tiers/trail/date/category", () => {
  const entry = {
    title: "Cut museum grant funding.",
    what_changed: "Funding was cut by 30%.",
    primary_proponent: { name: "Jane Doe", role: "Director", note: "Signed the order." },
    estimated_impact: { summary: "Programs for 500 people lost funding." },
    confidence_note: "Well sourced.",
    last_verified: "2026-08-01",
    date_of_action: "2026-02-01",
    date_added: "2026-02-10",
    domain: "funding_redirection",
    sources: [{ name: "Press release", url: "https://example.com/b" }],
  };
  const r = fns.adaptGovServicesEntry(entry);
  assert.equal(r.headline, "Cut museum grant funding.");
  assert.equal(r.tiers[0], "Funding was cut by 30%.");
  assert.match(r.tiers[1], /Jane Doe/);
  assert.match(r.tiers[2], /Programs for 500 people lost funding\./);
  assert.equal(r.date, "2026-02-01");
  assert.equal(r.tracker, "govservices");
  assert.equal(r.category, "funding_redirection");
});

test("adaptProsecutionEntry composes headline/tiers/trail (from evidence)/date/category", () => {
  const entry = {
    section_summaries: { incident_summary: "Official fired a watchdog." },
    incident_summary: "The official removed the inspector general without cause.",
    elements_required: ["No cause was given", "Statute requires 30 days notice"],
    evidence: [{ type: "public_record", description: "Letter of removal", source_url: "https://example.com/c" }],
    cause: "Part of a broader pattern.",
    rebuttal_anticipated: "They will claim performance issues.",
    comeback: "No performance record was ever cited.",
    confidence_note: "High confidence, court filing.",
    last_verified: "2026-07-01",
    date_added: "2026-06-01",
    offense_category: "Improper Removal",
  };
  const r = fns.adaptProsecutionEntry(entry);
  assert.equal(r.headline, "Official fired a watchdog.");
  assert.equal(r.tiers[0], "The official removed the inspector general without cause.");
  assert.match(r.tiers[1], /Letter of removal/);
  assert.match(r.tiers[2], /Part of a broader pattern\./);
  assert.equal(r.trail.sources[0].name, "Letter of removal");
  assert.equal(r.trail.sources[0].url, "https://example.com/c");
  assert.equal(r.date, "2026-07-01");
  assert.equal(r.tracker, "prosecution");
  assert.equal(r.category, "Improper Removal");
});

test("adaptCommunityTopicEntry composes headline/tiers/trail/date, category is null", () => {
  const entry = {
    topic: "A bill would require agency reporting.",
    summary: "The bill is real and in committee.",
    verdict: "confirmed",
    submitted_claim: "the bill is in committee",
    related_entries: [{ tracker: "government-services", id: "x", note: "same agency" }],
    sources: [{ name: "Congress.gov", url: "https://example.com/d" }],
    date_submitted: "2026-08-01",
    date_added: "2026-08-05",
  };
  const r = fns.adaptCommunityTopicEntry(entry);
  assert.equal(r.headline, "A bill would require agency reporting.");
  assert.equal(r.tiers[0], "The bill is real and in committee.");
  assert.match(r.tiers[1], /Confirmed/);
  assert.match(r.tiers[2], /the bill is in committee/);
  assert.equal(r.trail.confidenceNote, null);
  assert.equal(r.trail.lastVerified, null);
  assert.equal(r.date, "2026-08-01");
  assert.equal(r.tracker, "communitytopics");
  assert.equal(r.category, null);
});

test("adaptReportingEntry caps at 2 usable tiers (full collapses into medium)", () => {
  const entry = {
    what_happened: "An agency announced a new policy.",
    why_it_matters: "It affects millions of people.",
    source_name: "Local News",
    source_url: "https://example.com/e",
    date: "2026-05-01",
    category: "Executive Action",
  };
  const r = fns.adaptReportingEntry(entry);
  assert.equal(r.headline, "An agency announced a new policy.");
  assert.equal(r.tiers[0], "An agency announced a new policy.");
  assert.match(r.tiers[1], /It affects millions of people\./);
  assert.equal(r.tiers[2], r.tiers[1]);
  assert.equal(fns.usableTierCount(r.tiers), 2);
  assert.equal(r.trail.sources[0].name, "Local News");
  assert.equal(r.trail.confidenceNote, null);
  assert.equal(r.date, "2026-05-01");
  assert.equal(r.tracker, "tracker");
  assert.equal(r.category, "Executive Action");
});

test("adaptReportingEntry uses Uncategorized-safe null category when missing", () => {
  const r = fns.adaptReportingEntry({ what_happened: "x", date: "2026-01-01", category: null });
  assert.equal(r.category, null);
});

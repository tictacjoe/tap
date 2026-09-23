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
  "evidence-drawer",        // isRecheckNote / evidenceForSourceTrail, used by adaptProsecutionEntry
  "truncate",
  "verdict-label",
  "combine-tier-text",
  "fullest-tier-text",
  "pack-headline",
  "strip-process-labels",   // stripAdaptedItemLabels (below) calls stripProcessLabels
  "strip-adapted-item-labels", // every adapt*Entry() wraps its return in this
  "flatten-tracker-posts",  // Reporting's real shape: tracker.json is digests of dated entries, not flat posts
  "adapt-deregulation-entry",
  "adapt-govservices-entry",
  "adapt-prosecution-entry",
  "adapt-communitytopic-entry",
  "adapt-reporting-entry",
];
const combined = names.map(n => extractFunction(source, n)).join("\n");
const exposeNames = [
  "combineTierText", "fullestTierText", "packHeadline", "stripAdaptedItemLabels", "flattenTrackerPosts",
  "adaptDeregulationEntry", "adaptGovServicesEntry", "adaptProsecutionEntry",
  "adaptCommunityTopicEntry", "adaptReportingEntry",
];
const fns = (0, eval)(`${combined}\n({ ${exposeNames.join(", ")} });`);

test("combineTierText joins only non-empty parts with a space", () => {
  assert.equal(fns.combineTierText(["a", "", null, "b"]), "a b");
  assert.equal(fns.combineTierText(["", null, undefined]), "");
});

test("fullestTierText returns the last non-empty leading tier", () => {
  assert.equal(fns.fullestTierText(["a", "a b", "a b c"]), "a b c");
  assert.equal(fns.fullestTierText(["a", "a", "a"]), "a");
  assert.equal(fns.fullestTierText(["a", "a b", "a b"]), "a b");
  assert.equal(fns.fullestTierText(["", "x", "y"]), "");
});

test("packHeadline returns short text unchanged", () => {
  assert.equal(fns.packHeadline("Repealed the widget rule.", 110), "Repealed the widget rule.");
});

test("packHeadline cuts at the nearest sentence break within budget", () => {
  const text = "EPA rescinded the endangerment finding entirely. Vehicle emissions standards were repealed as a follow-on action affecting a much longer tail of downstream rules.";
  const result = fns.packHeadline(text, 60);
  assert.equal(result, "EPA rescinded the endangerment finding entirely.");
});

test("packHeadline cuts at a clause break (em-dash style) when no sentence break is in range", () => {
  const text = "DOJ's Public Integrity Section was cut from 36 attorneys to 2 -- while Trump pardoned 15 people convicted of public corruption over the same period";
  const result = fns.packHeadline(text, 70);
  assert.equal(result, "DOJ's Public Integrity Section was cut from 36 attorneys to 2");
});

test("packHeadline falls back to a word-boundary cut with an ellipsis when no natural break exists in range", () => {
  const text = "a".repeat(30) + " " + "b".repeat(30) + " " + "c".repeat(30) + " " + "d".repeat(30);
  const result = fns.packHeadline(text, 50);
  assert.ok(result.endsWith("…"));
  assert.ok(result.length <= 51);
  assert.ok(!result.slice(0, -1).includes(" ".repeat(2))); // sanity: no double-space artifact
});

test("packHeadline never returns an empty string for non-empty input", () => {
  assert.notEqual(fns.packHeadline("x".repeat(200), 50), "");
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
  assert.equal(r.date, "2026-01-01");
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
    date_of_action: "2026-05-01",
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
  assert.equal(r.date, "2026-05-01");
  assert.equal(r.tracker, "prosecution");
  assert.equal(r.category, "Improper Removal");
});

test("adaptProsecutionEntry leaves recheck notes out of the Sources trail unless a note is a link's only citation", () => {
  const r = fns.adaptProsecutionEntry({
    evidence: [
      { description: "Court order granting the injunction", source_url: "https://example.com/order" },
      { description: "Re-verified 2026-08-18: no new ruling identified.", source_url: "https://example.com/order" },   // same link as a source: redundant
      { description: "Re-verification 2026-09-02: still pending.", source_url: null },                                 // no link: nothing to lose
      { description: "Re-verified 2026-09-05: DOJ filed a notice of appeal.", source_url: "https://example.com/docket" }, // only place this link is cited
      { description: "Added 2026-09-09 (cluster c1): a later development was re-verified", source_url: "https://example.com/later" },
    ],
  });
  assert.deepEqual(r.trail.sources.map(s => s.url),
    ["https://example.com/order", "https://example.com/docket", "https://example.com/later"]);
  assert.equal(r.trail.sources[1].name, "Re-verified 2026-09-05: DOJ filed a notice of appeal.");
});

test("adaptProsecutionEntry falls back to date_added when date_of_action is missing", () => {
  const r = fns.adaptProsecutionEntry({ last_verified: "2026-07-01", date_added: "2026-06-01" });
  assert.equal(r.date, "2026-06-01");
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
  assert.equal(fns.fullestTierText(r.tiers), r.tiers[1]);
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

// Found 2026-09-22: stripProcessLabels() was never wired into these adapters, so a round-4
// backlog-fold label in the underlying raw text reached the Records feed's headline, its
// mouse-over tooltip (tiers[0]), and the Headlines trail panel (confidenceNote/sources),
// even though it was already hidden on the expanded detail card and in search. Every
// adapt*Entry() now wraps its return in stripAdaptedItemLabels().
test("stripAdaptedItemLabels strips headline, every tier, trail.confidenceNote and trail.sources[].name", () => {
  const item = {
    headline: "Agency acted (round-4 backlog cluster c0309) against schools.",
    tiers: [
      "Round-4 backlog fold, cluster c0509: The New York Times reported.",
      "Brief. Update 2026-08-02 (round 4 batch 27, cluster c0385): a recheck.",
      "Full text (cluster c1234) unaffected otherwise.",
    ],
    trail: {
      confidenceNote: "HIGH confidence (round-4 discovery fold).",
      sources: [{ name: "Evidence: Round-4 backlog fold, cluster c0284: WaPo reported.", url: "https://example.com" }],
    },
  };
  const stripped = fns.stripAdaptedItemLabels(item);
  assert.equal(stripped.headline, "Agency acted against schools.");
  assert.equal(stripped.tiers[0], "The New York Times reported.");
  assert.equal(stripped.tiers[1], "Brief. Update 2026-08-02: a recheck.", "only the parenthetical is removed; the entry's own Update DATE: marker stays");
  assert.equal(stripped.tiers[2], "Full text unaffected otherwise.");
  assert.equal(stripped.trail.confidenceNote, "HIGH confidence.");
  assert.equal(stripped.trail.sources[0].name, "Evidence: WaPo reported.");
  assert.equal(stripped.trail.sources[0].url, "https://example.com", "non-name fields on a source are untouched");
});

test("stripAdaptedItemLabels tolerates a trail with no confidenceNote/sources and returns the same item", () => {
  const item = { headline: "x", tiers: ["a", "b"], trail: {} };
  assert.equal(fns.stripAdaptedItemLabels(item), item);
});

for (const [kind, adaptFn, file] of [
  ["deregulation", "adaptDeregulationEntry", "deregulation.json"],
  ["govservices", "adaptGovServicesEntry", "government-services.json"],
  ["prosecution", "adaptProsecutionEntry", "prosecution.json"],
  ["communitytopics", "adaptCommunityTopicEntry", "community-topics.json"],
]) {
  test(`${kind}: no published entry's Records headline/tiers/trail still carries round-4 backlog-fold language`, () => {
    const data = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "data", file), "utf8"));
    // Same specific vocabulary as PROCESS_LABEL_WORDS in index.html (word-boundary'd),
    // not a bare "round 4" -- that alone false-positives on ordinary text like
    // "around 400 employees" ("round4" is a literal substring of "around 40...").
    const LEAK_RE = /\bround[\s-]?4\s+(backlog|batch|candidate|discovery|fold|cluster)|\bbacklog\s+(fold|cluster)|\bclusters?\s+c\d{3,4}\b/i;
    const leaks = [];
    for (const entry of data) {
      const item = fns[adaptFn](entry);
      const texts = [item.headline, ...(item.tiers || []), item.trail?.confidenceNote, ...((item.trail?.sources || []).map(s => s.name))];
      if (texts.some(t => t && LEAK_RE.test(t))) leaks.push(entry.id);
    }
    assert.deepEqual(leaks, [], `entries whose Records feed output still leaks round-4 language: ${leaks.join(", ")}`);
  });
}

// Reporting's own published shape is nested digests (tracker.json is a list of {date, entries:
// [...]} posts), not one row per entry -- flatten the same way loadAllData() does before adapting.
// Real Reporting posts are externally scraped news, not TAP's own process narration, so this is
// a belt-and-suspenders check, not an expected finding.
test("reporting: no flattened published post's Records headline/tiers still carries round-4 backlog-fold language", () => {
  const digests = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "data", "tracker.json"), "utf8"));
  const posts = fns.flattenTrackerPosts(digests);
  const LEAK_RE = /\bround[\s-]?4\s+(backlog|batch|candidate|discovery|fold|cluster)|\bbacklog\s+(fold|cluster)|\bclusters?\s+c\d{3,4}\b/i;
  const leaks = [];
  for (const post of posts) {
    const item = fns.adaptReportingEntry(post);
    if ([item.headline, ...item.tiers].some(t => t && LEAK_RE.test(t))) {
      leaks.push((post.post_title || "").slice(0, 60) + " @ " + post.date);
    }
  }
  assert.deepEqual(leaks, []);
});

// GSR/CDR Broader Pattern in the feed (2026-09-23 spec, sec-5 item 2): same
// "Pattern: " + cause as adaptProsecutionEntry, fullest tier only.
test("adaptGovServicesEntry appends 'Pattern: ' + cause to the fullest tier only, after impact", () => {
  const r = fns.adaptGovServicesEntry({ what_changed: "W.", estimated_impact: { summary: "I." }, cause: "[TAP Analysis, not sourced] P." });
  assert.equal(r.tiers[2], "W. Impact: I. Pattern: [TAP Analysis, not sourced] P.");
  assert(!r.tiers[1].includes("Pattern:"));
});

test("adaptGovServicesEntry without cause keeps its fullest tier unchanged", () => {
  const r = fns.adaptGovServicesEntry({ what_changed: "W.", estimated_impact: { summary: "I." } });
  assert.equal(r.tiers[2], "W. Impact: I.");
});

test("adaptDeregulationEntry appends 'Pattern: ' + cause to the fullest tier only, after stakes", () => {
  const r = fns.adaptDeregulationEntry({ what_changed: "W.", estimated_health_impact: { summary: "S." }, cause: "[TAP Analysis, not sourced] P." });
  assert.equal(r.tiers[2], "W. At stake: S. Pattern: [TAP Analysis, not sourced] P.");
  assert(!r.tiers[1].includes("Pattern:"));
});

test("adaptDeregulationEntry without cause keeps its fullest tier unchanged", () => {
  const r = fns.adaptDeregulationEntry({ what_changed: "W.", estimated_health_impact: { summary: "S." } });
  assert.equal(r.tiers[2], "W. At stake: S.");
});

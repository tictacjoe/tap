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

// Extract all the functions buildDetailHtml transitively depends on --
// summaryLineHtml for the curated trackers, escapeHtml/highlightMatches
// for the tracker (Reporting) kind's search-term highlighting.
const escapeHtmlFunctionSource = extractFunction(source, "escape-html");
const summaryLineFunctionSource = extractFunction(source, "summary-line");
const highlightMatchesFunctionSource = extractFunction(source, "highlight-matches");
const buildUpdateRequestHtmlFunctionSource = extractFunction(source, "build-update-request-html");
const paragraphizeUpdatesFunctionSource = extractFunction(source, "paragraphize-updates");
const buildDetailHtmlFunctionSource = extractFunction(source, "build-detail-html");

// Eval them all together so buildDetailHtml can call summaryLineHtml and
// highlightMatches (which itself calls escapeHtml/escapeRegExp), plus
// buildUpdateRequestHtml (which calls escapeHtml directly) and
// paragraphizeUpdates (used for the Cabinet-Level Status field).
const combined = escapeHtmlFunctionSource + "\n" + summaryLineFunctionSource + "\n" +
  highlightMatchesFunctionSource + "\n" + buildUpdateRequestHtmlFunctionSource + "\n" +
  paragraphizeUpdatesFunctionSource + "\n" + buildDetailHtmlFunctionSource;
const buildDetailHtml = (0, eval)(`${combined}\nbuildDetailHtml;`);

// paragraphizeUpdates has no dependencies of its own, so it's also
// evaluated standalone to test its marker regex directly rather than
// only through one field's wiring in buildDetailHtml.
const paragraphizeUpdates = (0, eval)(`${paragraphizeUpdatesFunctionSource}\nparagraphizeUpdates;`);
const identity = (text) => text || "";

test("deregulation with summaries", () => {
  const entry = {
    what_changed: "Agency repealed the rule.",
    estimated_health_impact: {
      summary: "Costs rise."
    },
    confidence_note: "High confidence.",
    section_summaries: {
      what_changed: "Repealed outright.",
      estimated_impact: "Costs rise for workers.",
      confidence_note: "Well-sourced."
    },
    primary_proponent: {
      name: "John Doe",
      role: "Administrator",
      note: ""
    },
    sources: []
  };
  const cfg = { kind: "deregulation" };
  const result = buildDetailHtml(entry, cfg);

  // Check that summary lines are present and come before the paragraph text
  assert(result.includes('<p class="field-summary">Repealed outright.</p>'), "should include what_changed summary");
  assert(result.includes('<p class="field-summary">Costs rise for workers.</p>'), "should include estimated_impact summary");
  assert(result.includes('<p class="field-summary">Well-sourced.</p>'), "should include confidence_note summary");

  // Verify they appear in the right order relative to their content
  const whatChangedIndex = result.indexOf("Repealed outright");
  const whatChangedContentIndex = result.indexOf("Agency repealed the rule");
  assert(whatChangedIndex < whatChangedContentIndex, "what_changed summary should come before content");

  const impactIndex = result.indexOf("Costs rise for workers");
  const impactContentIndex = result.indexOf("Costs rise.");
  assert(impactIndex < impactContentIndex, "estimated_impact summary should come before content");
});

test("deregulation without summaries (regression check)", () => {
  const entry = {
    what_changed: "Agency repealed the rule.",
    estimated_health_impact: {
      summary: "Costs rise."
    },
    confidence_note: "High confidence.",
    // NO section_summaries key at all
    primary_proponent: {
      name: "John Doe",
      role: "Administrator",
      note: ""
    },
    sources: []
  };
  const cfg = { kind: "deregulation" };
  const result = buildDetailHtml(entry, cfg);

  // Should contain ZERO field-summary elements
  assert.equal(
    (result.match(/class="field-summary"/g) || []).length,
    0,
    "should contain zero field-summary classes when no section_summaries"
  );
});

test("govservices with summaries", () => {
  const entry = {
    institution: "Department of Commerce",
    what_changed: "Reduced staffing by 30%.",
    estimated_impact: {
      summary: "Delayed processing times."
    },
    confidence_note: "Moderately confident.",
    section_summaries: {
      what_changed: "Major staffing reduction.",
      estimated_impact: "Processing will slow significantly.",
      confidence_note: "Multiple sources confirm."
    },
    primary_proponent: {
      name: "Jane Smith",
      role: "Secretary",
      note: ""
    },
    sources: []
  };
  const cfg = { kind: "govservices" };
  const result = buildDetailHtml(entry, cfg);

  // Check that summary lines are present
  assert(result.includes('<p class="field-summary">Major staffing reduction.</p>'), "should include what_changed summary");
  assert(result.includes('<p class="field-summary">Processing will slow significantly.</p>'), "should include estimated_impact summary");
  assert(result.includes('<p class="field-summary">Multiple sources confirm.</p>'), "should include confidence_note summary");

  // Verify they appear in the right order relative to their content
  const whatChangedIndex = result.indexOf("Major staffing reduction");
  const whatChangedContentIndex = result.indexOf("Reduced staffing by 30%");
  assert(whatChangedIndex < whatChangedContentIndex, "what_changed summary should come before content");
});

test("govservices (Government Service Redirection) highlights the search term throughout the body", () => {
  const entry = {
    institution: "U.S. Department of Education, Office for Civil Rights",
    what_changed: "Reduced staffing significantly.",
    estimated_impact: {
      summary: "Slower complaint processing.",
      caveat: "Civil rights groups dispute the agency's framing."
    },
    confidence_note: "Civil rights advocates corroborate the timeline.",
    primary_proponent: { name: "Jane Smith", role: "Secretary", note: "" },
    sources: []
  };
  const cfg = { kind: "govservices" };
  const result = buildDetailHtml(entry, cfg, "civil rights", false);

  // institution, caveat, and confidence_note each contain a separate
  // match of the phrase "civil rights" -- all three were previously
  // rendered raw/unhighlighted. Multi-word terms highlight each word
  // independently (matching matchesTerm()'s AND-of-words behavior), so
  // each of the 3 occurrences produces 2 <mark> tags.
  assert.equal(
    (result.match(/<mark class="hl">/g) || []).length,
    6,
    "should highlight the term in institution, caveat, and confidence_note"
  );
});

test("prosecution with summaries", () => {
  const entry = {
    offense_category: "Fraud",
    status_category: "Investigation",
    offense_category_raw: "18 USC § 1001",
    incident_summary: "False statements on federal forms.",
    status: "Under investigation by DOJ.",
    confidence_note: "Strong evidence.",
    section_summaries: {
      incident_summary: "Allegedly submitted fraudulent documents.",
      confidence_note: "Based on witness accounts and documents."
    }
  };
  const cfg = { kind: "prosecution" };
  const result = buildDetailHtml(entry, cfg);

  // Check that summary lines are present
  assert(result.includes('<p class="field-summary">Allegedly submitted fraudulent documents.</p>'), "should include incident_summary summary");
  assert(result.includes('<p class="field-summary">Based on witness accounts and documents.</p>'), "should include confidence_note summary");

  // Verify they appear in the right order relative to their content
  const incidentIndex = result.indexOf("Allegedly submitted fraudulent documents");
  const incidentContentIndex = result.indexOf("False statements on federal forms");
  assert(incidentIndex < incidentContentIndex, "incident_summary summary should come before content");
});

test("prosecution (Cabinet-Level) highlights the search term throughout the body", () => {
  const entry = {
    offense_category: "Civil Rights Violation",
    status_category: "Investigation",
    offense_category_raw: "42 USC 1983",
    incident_summary: "Alleged violation of civil rights during the raid.",
    status: "Under investigation.",
    confidence_note: "Civil rights attorneys corroborate the account.",
    cause: "A civil rights enforcement gap enabled this.",
    rebuttal_anticipated: "Officials may cite civil rights training as a defense.",
    comeback: "That civil rights training claim doesn't survive scrutiny."
  };
  const cfg = { kind: "prosecution" };
  const result = buildDetailHtml(entry, cfg, "civil rights", false);

  // offense_category, incident_summary, confidence_note, cause,
  // rebuttal_anticipated, and comeback each contain a separate match of
  // the phrase "civil rights" -- all six are rendered raw/unhighlighted
  // without this fix (only the card's collapsed meta line was hit for
  // the pre-existing fields; cause/rebuttal_anticipated/comeback weren't
  // rendered at all). Multi-word terms highlight each word independently
  // (matching matchesTerm()'s AND-of-words behavior), so each of the 6
  // occurrences produces 2 <mark> tags.
  assert.equal(
    (result.match(/<mark class="hl">/g) || []).length,
    12,
    "should highlight the term in offense_category, incident_summary, confidence_note, cause, rebuttal_anticipated, and comeback"
  );
});

test("prosecution renders Root Cause, Anticipated Defense, and TAP's Rebuttal after Confidence note", () => {
  const entry = {
    offense_category: "Fraud",
    status_category: "Investigation",
    offense_category_raw: "18 USC § 1001",
    incident_summary: "False statements on federal forms.",
    status: "Under investigation by DOJ.",
    confidence_note: "Strong evidence.",
    cause: "Structural incentive analysis goes here.",
    rebuttal_anticipated: "The likely defense goes here.",
    comeback: "Why that defense doesn't hold up goes here."
  };
  const cfg = { kind: "prosecution" };
  const result = buildDetailHtml(entry, cfg);

  assert(result.includes('<div class="field-label">Root Cause</div><div class="field-value">Structural incentive analysis goes here.</div>'), "should render cause under a Root Cause label");
  assert(result.includes('<div class="field-label">Anticipated Defense</div><div class="field-value">The likely defense goes here.</div>'), "should render rebuttal_anticipated under an Anticipated Defense label");
  assert(result.includes("<div class=\"field-label\">TAP's Rebuttal</div><div class=\"field-value\">Why that defense doesn't hold up goes here.</div>"), "should render comeback under a TAP's Rebuttal label");

  const confidenceIndex = result.indexOf("Confidence note");
  const causeIndex = result.indexOf("Root Cause");
  const rebuttalIndex = result.indexOf("Anticipated Defense");
  const comebackIndex = result.indexOf("TAP's Rebuttal");
  assert(confidenceIndex < causeIndex, "Root Cause should come after Confidence note");
  assert(causeIndex < rebuttalIndex, "Anticipated Defense should come after Root Cause");
  assert(rebuttalIndex < comebackIndex, "TAP's Rebuttal should come after Anticipated Defense");
});

test("prosecution Status field renders as a single paragraph when there are no Update markers", () => {
  const entry = {
    offense_category: "Fraud",
    status_category: "Investigation",
    incident_summary: "Summary.",
    status: "Under investigation by DOJ.",
    confidence_note: "Strong evidence.",
  };
  const cfg = { kind: "prosecution" };
  const result = buildDetailHtml(entry, cfg);

  assert(
    result.includes('<div class="field-label">Status</div><div class="field-value"><p>Under investigation by DOJ.</p></div>'),
    "status with no Update marker should render as one <p> inside field-value"
  );
});

test("prosecution Status field splits into separate paragraphs at each Update marker", () => {
  const entry = {
    offense_category: "Fraud",
    status_category: "Investigation",
    incident_summary: "Summary.",
    status: "Initial finding here. Update 2026-07-26: first update text. Update 2026-08-02 (real correction): second update text.",
    confidence_note: "Strong evidence.",
  };
  const cfg = { kind: "prosecution" };
  const result = buildDetailHtml(entry, cfg);

  const statusStart = result.indexOf('<div class="field-label">Status</div><div class="field-value">');
  const statusEnd = result.indexOf('<div class="field-label">Confidence note</div>');
  const statusHtml = result.slice(statusStart, statusEnd);

  assert.equal((statusHtml.match(/<p>/g) || []).length, 3, "should split into 3 paragraphs, one per Update marker plus the lead-in text");
  assert(statusHtml.includes("<p>Initial finding here.</p>"), "lead-in text before the first marker should be its own paragraph");
  assert(statusHtml.includes("<p>Update 2026-07-26: first update text.</p>"), "each Update marker should start its own paragraph");
  assert(statusHtml.includes("<p>Update 2026-08-02 (real correction): second update text.</p>"), "an annotated Update marker should also start its own paragraph");
});

test("prosecution Status field does not false-split on a forward self-reference like \"(see Update below)\"", () => {
  const entry = {
    offense_category: "Fraud",
    status_category: "Investigation",
    incident_summary: "Summary.",
    status: "The DOJ did not appeal (see Update below). No charges have been filed against Powell as of this entry Update: Powell's chair term ended May 15, 2026.",
    confidence_note: "Strong evidence.",
  };
  const cfg = { kind: "prosecution" };
  const result = buildDetailHtml(entry, cfg);

  const statusStart = result.indexOf('<div class="field-label">Status</div><div class="field-value">');
  const statusEnd = result.indexOf('<div class="field-label">Confidence note</div>');
  const statusHtml = result.slice(statusStart, statusEnd);

  assert.equal((statusHtml.match(/<p>/g) || []).length, 2, "the parenthetical \"(see Update below)\" mention must not itself start a paragraph");
  assert(
    statusHtml.includes("<p>The DOJ did not appeal (see Update below). No charges have been filed against Powell as of this entry</p>"),
    "text up to the real Update marker should stay one paragraph, including the false-positive mention"
  );
  assert(
    statusHtml.includes("<p>Update: Powell's chair term ended May 15, 2026.</p>"),
    "the real, colon-terminated Update marker should start the second paragraph"
  );
});

test("paragraphizeUpdates splits on an Added marker (round-4 backlog-fold convention used in government-services/deregulation what_changed fields)", () => {
  const text = "Original narrative here. Added 2026-09-10 (round-4 backlog cluster c0309): first fold addition. Added 2026-09-09 (round-4 backlog cluster c0574): second fold addition.";
  const result = paragraphizeUpdates(text, identity);

  assert.equal((result.match(/<p>/g) || []).length, 3, "should split into 3 paragraphs, one per Added marker plus the lead-in text");
  assert(result.includes("<p>Original narrative here.</p>"), "lead-in text before the first marker should be its own paragraph");
  assert(result.includes("<p>Added 2026-09-10 (round-4 backlog cluster c0309): first fold addition.</p>"), "each Added marker should start its own paragraph");
  assert(result.includes("<p>Added 2026-09-09 (round-4 backlog cluster c0574): second fold addition.</p>"), "a second Added marker should also start its own paragraph");
});

test("paragraphizeUpdates splits correctly when Update and Added markers are mixed in the same field", () => {
  const text = "Original narrative. Update 2026-08-17: a recheck update. Added 2026-09-10 (round-4 backlog cluster c0309): a fold addition.";
  const result = paragraphizeUpdates(text, identity);

  assert.equal((result.match(/<p>/g) || []).length, 3, "Update and Added markers should each start their own paragraph, same as same-word markers do");
  assert(result.includes("<p>Update 2026-08-17: a recheck update.</p>"), "an Update marker should still split correctly when Added markers are also present");
  assert(result.includes("<p>Added 2026-09-10 (round-4 backlog cluster c0309): a fold addition.</p>"), "an Added marker should split correctly when Update markers are also present");
});

test("prosecution Status field does not false-split on a forward self-reference like \"(see Added below)\"", () => {
  const entry = {
    offense_category: "Fraud",
    status_category: "Investigation",
    incident_summary: "Summary.",
    status: "The DOJ did not appeal (see Added detail below). No charges have been filed against Powell as of this entry Added: new detail follows here.",
    confidence_note: "Strong evidence.",
  };
  const cfg = { kind: "prosecution" };
  const result = buildDetailHtml(entry, cfg);

  const statusStart = result.indexOf('<div class="field-label">Status</div><div class="field-value">');
  const statusEnd = result.indexOf('<div class="field-label">Confidence note</div>');
  const statusHtml = result.slice(statusStart, statusEnd);

  assert.equal((statusHtml.match(/<p>/g) || []).length, 2, "the parenthetical \"(see Added detail below)\" mention must not itself start a paragraph");
  assert(
    statusHtml.includes("<p>The DOJ did not appeal (see Added detail below). No charges have been filed against Powell as of this entry</p>"),
    "text up to the real Added marker should stay one paragraph, including the false-positive mention"
  );
  assert(
    statusHtml.includes("<p>Added: new detail follows here.</p>"),
    "the real, colon-terminated Added marker should start the second paragraph"
  );
});

test("tracker (Reporting) highlights the search term in the body", () => {
  const entry = {
    what_happened: "The EPA announced new rules today.",
    source_name: "Example Substack",
    source_url: "https://example.com/post",
  };
  const cfg = { kind: "tracker" };
  const result = buildDetailHtml(entry, cfg, "EPA", false);

  assert(
    result.includes('<mark class="hl">EPA</mark>'),
    "should wrap the matched term in the body text with a <mark> highlight"
  );
});

test("tracker (Reporting) highlights the search term inside the source name", () => {
  const entry = {
    what_happened: "Some unrelated announcement.",
    source_name: "Civil Rights Group Sues Over New Policy",
    source_url: "https://example.com/post",
  };
  const cfg = { kind: "tracker" };
  const result = buildDetailHtml(entry, cfg, "civil rights", false);

  assert(
    result.includes('<mark class="hl">Civil Rights</mark>'),
    "should wrap the matched term in the source name with a <mark> highlight"
  );
});

test("tracker (Reporting) with no active search term leaves body unhighlighted but escaped", () => {
  const entry = {
    what_happened: "Rules & <regulations> changed.",
    source_name: "",
  };
  const cfg = { kind: "tracker" };
  const result = buildDetailHtml(entry, cfg, "", false);

  assert(!result.includes('<mark class="hl">'), "should not highlight anything when no term is active");
  assert(result.includes("Rules &amp; &lt;regulations&gt; changed."), "should still HTML-escape the raw body text");
});

test("deregulation shows last verified date and a request-update button", () => {
  const entry = {
    id: "some-rule-id",
    rule_name: "Some Rule",
    last_verified: "2026-08-01",
    primary_proponent: {},
    estimated_health_impact: {},
  };
  const cfg = { kind: "deregulation", idField: "id", titleField: "rule_name" };
  const result = buildDetailHtml(entry, cfg);

  assert(result.includes('<span class="field-value">Last verified 2026-08-01</span>'), "should show the last_verified date");
  assert(result.includes('class="suggest-submit-btn request-update-btn"'), "should include the request-update button");
  assert(result.includes('data-tracker="deregulation"'), "button should carry the tracker key");
  assert(result.includes('data-entry-id="some-rule-id"'), "button should carry the entry id");
  assert(result.includes('data-entry-title="Some Rule"'), "button should carry the entry title");
  assert(result.includes('data-last-verified="2026-08-01"'), "button should carry the current last_verified date, so the click-time lock can detect a later recheck");
});

test("prosecution falls back to a placeholder when last_verified is missing", () => {
  const entry = {
    id: "some-official-id",
    official: "Some Official, Some Title",
    offense_category: "Fraud",
    status_category: "Investigation",
    incident_summary: "Summary.",
    status: "Under investigation.",
    confidence_note: "Strong evidence.",
  };
  const cfg = { kind: "prosecution", idField: "id", titleField: "official" };
  const result = buildDetailHtml(entry, cfg);

  assert(result.includes('<span class="field-value">Last verified not yet recorded</span>'), "should show the fallback text when last_verified is absent");
  assert(result.includes('data-last-verified=""'), "should carry an empty data-last-verified when the entry has no last_verified value");
});

test("govservices request-update button carries the correct tracker and entry id", () => {
  const entry = {
    id: "some-action-id",
    title: "Some Action",
    institution: "Some Agency",
    last_verified: "2026-07-15",
    estimated_impact: {},
  };
  const cfg = { kind: "govservices", idField: "id", titleField: "title" };
  const result = buildDetailHtml(entry, cfg);

  assert(result.includes('<span class="field-value">Last verified 2026-07-15</span>'), "should show the last_verified date");
  assert(result.includes('data-tracker="govservices"'), "button should carry the govservices tracker key");
  assert(result.includes('data-entry-id="some-action-id"'), "button should carry the entry id");
});

test("paragraphizeUpdates splits on an Update marker with a long parenthetical annotation (regression for the old 60-char cap)", () => {
  // Real production shape from government-services/entries -- an
  // annotation like "(correction -- this entry's original 'litigation
  // ongoing' framing is now outdated)" runs well past 60 characters
  // before its colon, which the original cap missed entirely.
  const text = "Original finding here. Update 2026-08-17 (correction -- this entry's original 'litigation ongoing' framing is now outdated): the court declined to block the order.";
  const result = paragraphizeUpdates(text, identity);

  assert.equal((result.match(/<p>/g) || []).length, 2, "the long-annotation marker should still start its own paragraph");
  assert(result.includes("<p>Original finding here.</p>"), "lead-in text should be its own paragraph");
  assert(
    result.includes("<p>Update 2026-08-17 (correction -- this entry's original 'litigation ongoing' framing is now outdated): the court declined to block the order.</p>"),
    "the long-annotation Update marker should start the second paragraph"
  );
});

test("prosecution Incident summary renders as a single paragraph when there are no Update markers", () => {
  const entry = {
    offense_category: "Fraud",
    status_category: "Investigation",
    incident_summary: "False statements on federal forms.",
    status: "Under investigation.",
    confidence_note: "Strong evidence.",
  };
  const cfg = { kind: "prosecution" };
  const result = buildDetailHtml(entry, cfg);

  assert(
    result.includes('<div class="field-label">Incident summary</div><div class="field-value"><p>False statements on federal forms.</p></div>'),
    "incident_summary with no Update marker should render as one <p> inside field-value"
  );
});

test("prosecution Incident summary splits into separate paragraphs at each Update marker", () => {
  const entry = {
    offense_category: "Fraud",
    status_category: "Investigation",
    incident_summary: "Initial account here. Update 2026-07-26: additional detail surfaced.",
    status: "Under investigation.",
    confidence_note: "Strong evidence.",
  };
  const cfg = { kind: "prosecution" };
  const result = buildDetailHtml(entry, cfg);

  const start = result.indexOf('<div class="field-label">Incident summary</div><div class="field-value">');
  const end = result.indexOf('<div class="field-label">Status</div>');
  const html = result.slice(start, end);

  assert.equal((html.match(/<p>/g) || []).length, 2, "should split into 2 paragraphs, one per Update marker plus the lead-in text");
  assert(html.includes("<p>Initial account here.</p>"), "lead-in text before the marker should be its own paragraph");
  assert(html.includes("<p>Update 2026-07-26: additional detail surfaced.</p>"), "the Update marker should start its own paragraph");
});

test("govservices What changed renders as a single paragraph when there are no Update markers", () => {
  const entry = {
    institution: "Some Agency",
    what_changed: "Reduced staffing by 30%.",
    estimated_impact: {},
    confidence_note: "Moderately confident.",
  };
  const cfg = { kind: "govservices" };
  const result = buildDetailHtml(entry, cfg);

  assert(
    result.includes('<div class="field-label">What changed</div><div class="field-value"><p>Reduced staffing by 30%.</p></div>'),
    "what_changed with no Update marker should render as one <p> inside field-value"
  );
});

test("govservices What changed splits into separate paragraphs at each Update marker", () => {
  const entry = {
    institution: "Some Agency",
    what_changed: "Initial cuts announced. Update 2026-08-02: further reductions confirmed.",
    estimated_impact: {},
    confidence_note: "Moderately confident.",
  };
  const cfg = { kind: "govservices" };
  const result = buildDetailHtml(entry, cfg);

  const start = result.indexOf('<div class="field-label">What changed</div><div class="field-value">');
  const end = result.indexOf('<div class="field-label">Primary proponent</div>');
  const html = result.slice(start, end);

  assert.equal((html.match(/<p>/g) || []).length, 2, "should split into 2 paragraphs, one per Update marker plus the lead-in text");
  assert(html.includes("<p>Initial cuts announced.</p>"), "lead-in text before the marker should be its own paragraph");
  assert(html.includes("<p>Update 2026-08-02: further reductions confirmed.</p>"), "the Update marker should start its own paragraph");
});

test("deregulation What changed renders as a single paragraph when there are no Update markers", () => {
  const entry = {
    what_changed: "Agency repealed the rule.",
    estimated_health_impact: {},
    confidence_note: "High confidence.",
    primary_proponent: {},
  };
  const cfg = { kind: "deregulation" };
  const result = buildDetailHtml(entry, cfg);

  assert(
    result.includes('<div class="field-label">What changed</div><div class="field-value"><p>Agency repealed the rule.</p></div>'),
    "what_changed with no Update marker should render as one <p> inside field-value"
  );
});

test("deregulation What changed splits into separate paragraphs at each Update marker", () => {
  const entry = {
    what_changed: "Rule repealed outright. Update 2026-08-02: a challenge was filed.",
    estimated_health_impact: {},
    confidence_note: "High confidence.",
    primary_proponent: {},
  };
  const cfg = { kind: "deregulation" };
  const result = buildDetailHtml(entry, cfg);

  const start = result.indexOf('<div class="field-label">What changed</div><div class="field-value">');
  const end = result.indexOf('<div class="field-label">Primary proponent</div>');
  const html = result.slice(start, end);

  assert.equal((html.match(/<p>/g) || []).length, 2, "should split into 2 paragraphs, one per Update marker plus the lead-in text");
  assert(html.includes("<p>Rule repealed outright.</p>"), "lead-in text before the marker should be its own paragraph");
  assert(html.includes("<p>Update 2026-08-02: a challenge was filed.</p>"), "the Update marker should start its own paragraph");
});

test("prosecution Confidence note splits into separate paragraphs at each Update marker", () => {
  const entry = {
    offense_category: "Fraud",
    status_category: "Investigation",
    incident_summary: "Summary.",
    status: "Under investigation.",
    confidence_note: "Well-sourced initially. Update 2026-08-02: a second outlet corroborated.",
  };
  const cfg = { kind: "prosecution" };
  const result = buildDetailHtml(entry, cfg);

  const start = result.indexOf('<div class="field-label">Confidence note</div><div class="confidence-box">');
  const end = result.indexOf('<div class="field-label">Root Cause</div>');
  const html = result.slice(start, end);

  assert.equal((html.match(/<p>/g) || []).length, 2, "should split into 2 paragraphs, one per Update marker plus the lead-in text");
  assert(html.includes("<p>Well-sourced initially.</p>"), "lead-in text before the marker should be its own paragraph");
  assert(html.includes("<p>Update 2026-08-02: a second outlet corroborated.</p>"), "the Update marker should start its own paragraph");
});

test("govservices Confidence note splits into separate paragraphs at each Update marker", () => {
  const entry = {
    institution: "Some Agency",
    what_changed: "Reduced staffing.",
    estimated_impact: {},
    confidence_note: "Well-sourced initially. Update 2026-08-02: a second outlet corroborated.",
  };
  const cfg = { kind: "govservices" };
  const result = buildDetailHtml(entry, cfg);

  const start = result.indexOf('<div class="field-label">Confidence note</div><div class="confidence-box">');
  const end = result.indexOf('<div class="field-label">Sources</div>');
  const html = result.slice(start, end);

  assert.equal((html.match(/<p>/g) || []).length, 2, "should split into 2 paragraphs, one per Update marker plus the lead-in text");
  assert(html.includes("<p>Well-sourced initially.</p>"), "lead-in text before the marker should be its own paragraph");
  assert(html.includes("<p>Update 2026-08-02: a second outlet corroborated.</p>"), "the Update marker should start its own paragraph");
});

test("deregulation Confidence note splits into separate paragraphs at each Update marker", () => {
  const entry = {
    what_changed: "Rule repealed outright.",
    estimated_health_impact: {},
    primary_proponent: {},
    confidence_note: "Well-sourced initially. Update 2026-08-02: a second outlet corroborated.",
  };
  const cfg = { kind: "deregulation" };
  const result = buildDetailHtml(entry, cfg);

  const start = result.indexOf('<div class="field-label">Confidence note</div><div class="confidence-box">');
  const end = result.indexOf('<div class="field-label">Sources</div>');
  const html = result.slice(start, end);

  assert.equal((html.match(/<p>/g) || []).length, 2, "should split into 2 paragraphs, one per Update marker plus the lead-in text");
  assert(html.includes("<p>Well-sourced initially.</p>"), "lead-in text before the marker should be its own paragraph");
  assert(html.includes("<p>Update 2026-08-02: a second outlet corroborated.</p>"), "the Update marker should start its own paragraph");
});

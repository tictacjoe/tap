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
const buildConfidenceNoteHtmlFunctionSource = extractFunction(source, "build-confidence-note-html");
const buildDetailHtmlFunctionSource = extractFunction(source, "build-detail-html");
// Added 2026-09-19: buildDetailHtml gained two more direct dependencies
// with the 2026-09-18 columnar layout (safeHref for source links,
// buildPullQuoteHtml for the pull-quote) that this harness never picked
// up, so 26 of these tests were failing with ReferenceErrors before any
// layout work started.
const safeHrefFunctionSource = extractFunction(source, "safe-href");
const buildPullQuoteHtmlFunctionSource = extractFunction(source, "build-pull-quote-html");
const buildEntryColsHtmlFunctionSource = extractFunction(source, "build-entry-cols-html");

// safeHref resolves relative URLs against location.href, which doesn't
// exist in Node -- give it a fixed base so absolute test URLs round-trip.
globalThis.location = { href: "https://example.test/" };

// buildFiguresHtml drags in a whole categorization chain (figureCategory,
// FIGURE_CATEGORY_ORDER, isFigureSavings, ...) that has nothing to do
// with what these tests check. A placeholder keeps figures' *placement*
// (which column the card lands in) testable without evaluating that
// chain; the grouping logic itself isn't covered here.
const buildFiguresHtmlStubSource = "function buildFiguresHtml(figs) { return figs && figs.length ? '<!--figures:' + figs.length + '-->' : ''; }";

// Eval them all together so buildDetailHtml can call summaryLineHtml and
// highlightMatches (which itself calls escapeHtml/escapeRegExp), plus
// buildUpdateRequestHtml (which calls escapeHtml directly),
// paragraphizeUpdates (used for the Cabinet-Level Status/Incident summary
// fields), and buildConfidenceNoteHtml (used for the Confidence note
// field on all three curated-tracker kinds; calls escapeHtml directly).
const combined = escapeHtmlFunctionSource + "\n" + summaryLineFunctionSource + "\n" +
  highlightMatchesFunctionSource + "\n" + buildUpdateRequestHtmlFunctionSource + "\n" +
  paragraphizeUpdatesFunctionSource + "\n" + buildConfidenceNoteHtmlFunctionSource + "\n" +
  safeHrefFunctionSource + "\n" + buildPullQuoteHtmlFunctionSource + "\n" + buildEntryColsHtmlFunctionSource + "\n" +
  buildFiguresHtmlStubSource + "\n" + buildDetailHtmlFunctionSource;
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

test("prosecution renders Broader Pattern, Anticipated Defense, and TAP's Rebuttal in the main column, ahead of the sidebar's Confidence note", () => {
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

  assert(result.includes('<div class="field-label">Broader Pattern</div><div class="field-value">Structural incentive analysis goes here.</div>'), "should render cause under a Broader Pattern label");
  assert(result.includes('<div class="field-label">Anticipated Defense</div><div class="field-value">The likely defense goes here.</div>'), "should render rebuttal_anticipated under an Anticipated Defense label");
  assert(result.includes("<div class=\"field-label\">TAP's Rebuttal</div><div class=\"field-value\">Why that defense doesn't hold up goes here.</div>"), "should render comeback under a TAP's Rebuttal label");

  const confidenceIndex = result.indexOf("Confidence note");
  const causeIndex = result.indexOf("Broader Pattern");
  const rebuttalIndex = result.indexOf("Anticipated Defense");
  const comebackIndex = result.indexOf("TAP's Rebuttal");
  assert(causeIndex < confidenceIndex, "the main column (Broader Pattern) precedes the sidebar's Confidence note in the DOM");
  assert(causeIndex < rebuttalIndex, "Anticipated Defense should come after Broader Pattern");
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
    result.includes('<mark class="hl">Civil</mark> <mark class="hl">Rights</mark>'),
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

  assert(result.includes('<span class="field-value">Last updated and verified 2026-08-01</span>'), "should show the last_verified date");
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

  assert(result.includes('<span class="field-value">Last updated and verified not yet recorded</span>'), "should show the fallback text when last_verified is absent");
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

  assert(result.includes('<span class="field-value">Last updated and verified 2026-07-15</span>'), "should show the last_verified date");
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
    result.includes('<div class="field-label">What happened</div><div class="field-value"><p>Reduced staffing by 30%.</p></div>'),
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

  const start = result.indexOf('<div class="field-label">What happened</div><div class="field-value">');
  const end = result.indexOf('<div class="field-label">Estimated impact</div>');
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

test("prosecution Confidence note splits its base text from a separate Updates section, dated by heading", () => {
  const entry = {
    offense_category: "Fraud",
    status_category: "Investigation",
    incident_summary: "Summary.",
    status: "Under investigation.",
    confidence_note: "Initially sourced to one outlet. Update 2026-08-02: a second outlet corroborated.",
  };
  const cfg = { kind: "prosecution" };
  const result = buildDetailHtml(entry, cfg);

  const confidenceStart = result.indexOf('<div class="field-label">Confidence note</div><div class="confidence-box">');
  const updatesStart = result.indexOf('<div class="field-label">Updates</div>');
  const causeStart = result.indexOf('<div class="field-label">Broader Pattern</div>');

  assert(confidenceStart !== -1 && updatesStart !== -1 && causeStart !== -1, "all three sections should be present");
  assert(causeStart < confidenceStart && confidenceStart < updatesStart, "main column (Broader Pattern) precedes the sidebar's Confidence note, which precedes its Updates");

  const confidenceHtml = result.slice(confidenceStart, updatesStart);
  assert(confidenceHtml.includes("<p>Initially sourced to one outlet.</p>"), "the base text before the marker stays in the Confidence note box");
  assert(!confidenceHtml.includes("2026-08-02"), "the dated update should not remain in the Confidence note box");

  const updatesHtml = result.slice(updatesStart);
  assert(updatesHtml.includes('<div class="update-date">2026-08-02</div>'), "the update's date should render as its heading");
  assert(updatesHtml.includes("<p>Update 2026-08-02: a second outlet corroborated.</p>"), "the update's own text should render under its date heading");
});

test("prosecution Confidence note renders no Updates section when it has no Update/Added markers", () => {
  const entry = {
    offense_category: "Fraud",
    status_category: "Investigation",
    incident_summary: "Summary.",
    status: "Under investigation.",
    confidence_note: "Single outlet, no dispute.",
  };
  const cfg = { kind: "prosecution" };
  const result = buildDetailHtml(entry, cfg);

  assert(!result.includes('<div class="field-label">Updates</div>'), "no Updates section should render when there's nothing to put in it");
  assert(result.includes("<p>Single outlet, no dispute.</p>"), "the whole note stays in the Confidence note box");
});

test("govservices Confidence note splits into separate paragraphs at each Update marker", () => {
  const entry = {
    institution: "Some Agency",
    what_changed: "Reduced staffing.",
    estimated_impact: {},
    confidence_note: "Initially sourced to one outlet. Update 2026-08-02: a second outlet corroborated.",
  };
  const cfg = { kind: "govservices" };
  const result = buildDetailHtml(entry, cfg);

  const start = result.indexOf('<div class="field-label">Confidence note</div><div class="confidence-box">');
  // Sources moved out of the way in the 2026-09-19 three-column split: it
  // now sits in .entry-aside, *before* the Confidence note's .entry-note
  // column, so the note runs until the update-request row that follows
  // the columns.
  const end = result.indexOf('<div class="update-request-row">');
  const html = result.slice(start, end);

  assert.equal((html.match(/<p>/g) || []).length, 2, "should split into 2 paragraphs, one per Update marker plus the lead-in text");
  assert(html.includes("<p>Initially sourced to one outlet.</p>"), "lead-in text before the marker should be its own paragraph");
  assert(html.includes("<p>Update 2026-08-02: a second outlet corroborated.</p>"), "the Update marker should start its own paragraph");
});

test("deregulation Confidence note splits into separate paragraphs at each Update marker", () => {
  const entry = {
    what_changed: "Rule repealed outright.",
    estimated_health_impact: {},
    primary_proponent: {},
    confidence_note: "Initially sourced to one outlet. Update 2026-08-02: a second outlet corroborated.",
  };
  const cfg = { kind: "deregulation" };
  const result = buildDetailHtml(entry, cfg);

  const start = result.indexOf('<div class="field-label">Confidence note</div><div class="confidence-box">');
  // Sources moved out of the way in the 2026-09-19 three-column split: it
  // now sits in .entry-aside, *before* the Confidence note's .entry-note
  // column, so the note runs until the update-request row that follows
  // the columns.
  const end = result.indexOf('<div class="update-request-row">');
  const html = result.slice(start, end);

  assert.equal((html.match(/<p>/g) || []).length, 2, "should split into 2 paragraphs, one per Update marker plus the lead-in text");
  assert(html.includes("<p>Initially sourced to one outlet.</p>"), "lead-in text before the marker should be its own paragraph");
  assert(html.includes("<p>Update 2026-08-02: a second outlet corroborated.</p>"), "the Update marker should start its own paragraph");
});

// ---- Even card distribution across columns (2026-09-19) --------------
// Expanded curated-tracker entries render as .entry-cols holding three
// generic .entry-col containers. The markup puts EVERY card into the first
// one, in reading order; a script (distributeEntryCards) then measures the
// cards and moves each into whichever visible column is currently
// shortest. assignCardsToColumns is the pure "which column" decision,
// tested here in isolation; the DOM moving itself is checked in-browser.
const assignCardsToColumns = (0, eval)(`${extractFunction(source, "assign-cards-to-columns")}\nassignCardsToColumns;`);

test("assignCardsToColumns puts everything in column 0 when there is one column", () => {
  assert.deepEqual(assignCardsToColumns([100, 50, 80], 1, 10), [0, 0, 0]);
});

test("assignCardsToColumns spreads equal cards left to right across the columns", () => {
  assert.deepEqual(assignCardsToColumns([50, 50, 50], 3, 0), [0, 1, 2]);
  assert.deepEqual(assignCardsToColumns([50, 50, 50, 50], 3, 0), [0, 1, 2, 0]);
});

test("assignCardsToColumns sends each card to the currently shortest column", () => {
  // One tall card in column 0; the four short ones all fit under column 1's
  // running total before it catches up (30, 60, 90, then 120 > 100).
  assert.deepEqual(assignCardsToColumns([100, 30, 30, 30, 30], 2, 0), [0, 1, 1, 1, 1]);
});

test("assignCardsToColumns breaks ties toward the leftmost column", () => {
  assert.deepEqual(assignCardsToColumns([50, 50], 3, 0), [0, 1]);
});

test("assignCardsToColumns counts the gap between stacked cards", () => {
  // Column 1 is at 85, then 85+20+10 = 115 after its second card, so the
  // last card belongs in column 0 (100). With no gap it would be 95 and
  // column 1 would win again -- this pins that the gap is included.
  assert.deepEqual(assignCardsToColumns([100, 85, 10, 10], 2, 20), [0, 1, 1, 0]);
  assert.deepEqual(assignCardsToColumns([100, 85, 10, 10], 2, 0), [0, 1, 1, 1]);
});

test("assignCardsToColumns handles no cards and a nonsense column count", () => {
  assert.deepEqual(assignCardsToColumns([], 3, 10), []);
  assert.deepEqual(assignCardsToColumns([10, 20], 0, 10), [0, 0]);
});

const layoutEntries = {
  deregulation: {
    cfg: { kind: "deregulation" },
    entry: {
      what_changed: "Agency repealed the rule.",
      estimated_health_impact: { summary: "Costs rise.", caveat: "Modeled.", figures: [{ metric: "m", value: "1", source: "s" }] },
      confidence_note: "High confidence.",
      pull_quote: "A striking quote.",
      primary_proponent: { name: "John Doe", role: "Administrator", note: "" },
      sources: [{ name: "Src One", url: "https://example.com/1" }],
    },
    // Labels in the order a reader meets them: narrative cards, then data
    // cards, then the Confidence note, then the pull-quote.
    order: [">What changed</div>", ">Estimated impact</div>", ">Caveat</div>", ">Primary proponent</div>", "<!--figures:1-->", ">Sources</div>", ">Confidence note</div>", "entry-aside-quote"],
  },
  govservices: {
    cfg: { kind: "govservices" },
    entry: {
      institution: "Some Agency",
      what_changed: "Reduced staffing by 30%.",
      estimated_impact: { summary: "Delays.", caveat: "Estimate.", figures: [{ metric: "m", value: "1", source: "s" }] },
      confidence_note: "Moderately confident.",
      pull_quote: "A striking quote.",
      primary_proponent: { name: "Jane Smith", role: "Secretary", note: "" },
      sources: [{ name: "Src One", url: "https://example.com/1" }],
    },
    order: [">What happened</div>", ">Estimated impact</div>", ">Caveat</div>", ">Institution</div>", ">Primary proponent</div>", "<!--figures:1-->", ">Sources</div>", ">Confidence note</div>", "entry-aside-quote"],
  },
  prosecution: {
    cfg: { kind: "prosecution" },
    entry: {
      offense_category: "Fraud",
      status_category: "Investigation",
      offense_category_raw: "18 USC 1001",
      incident_summary: "Summary.",
      status: "Under investigation.",
      confidence_note: "Strong evidence.",
      pull_quote: "A striking quote.",
      cause: "Pattern.",
      rebuttal_anticipated: "Defense.",
      comeback: "Rebuttal.",
    },
    order: [">Violation Type (in full)</div>", ">Incident summary</div>", ">Status</div>", ">Broader Pattern</div>", ">Anticipated Defense</div>", ">TAP's Rebuttal</div>", ">Violation Type</div>", ">Status Stage</div>", ">Confidence note</div>", "entry-aside-quote"],
  },
};

for (const [kind, { cfg, entry, order }] of Object.entries(layoutEntries)) {
  test(`${kind} renders .entry-cols as three generic columns with every card in the first`, () => {
    const result = buildDetailHtml(entry, cfg);
    assert(result.startsWith('<div class="entry-cols"><div class="entry-col">'), "entry-cols should open onto the first entry-col");
    assert(result.includes('</div><div class="entry-col"></div><div class="entry-col"></div></div>'), "columns 2 and 3 start empty; the script fills them once the card is open");
    assert.equal((result.match(/<div class="entry-col">/g) || []).length, 3, "exactly three columns");
  });

  test(`${kind} no longer emits the old fixed-role column classes`, () => {
    const result = buildDetailHtml(entry, cfg);
    assert(!result.includes('class="entry-main"'), "entry-main column is gone");
    assert(!result.includes('class="entry-aside"'), "entry-aside column is gone");
    assert(!result.includes('class="entry-note"'), "entry-note column is gone");
  });

  test(`${kind} keeps its cards in reading order (narrative, data cards, Confidence note, quote last)`, () => {
    const result = buildDetailHtml(entry, cfg);
    let last = -1;
    for (const marker of order) {
      const at = result.indexOf(marker);
      assert(at !== -1, `card marker missing: ${marker}`);
      assert(at > last, `${marker} should come after the previous card in reading order`);
      last = at;
    }
  });
}

test("an entry with no pull_quote renders no quote element anywhere", () => {
  const { cfg, entry } = layoutEntries.govservices;
  const { pull_quote, ...withoutQuote } = entry;
  assert(!buildDetailHtml(withoutQuote, cfg).includes("entry-aside-quote"), "no quote markup when pull_quote is unset");
});

// ---- Bold confidence ratings (2026-09-19) -----------------------------
// Confidence notes often carry several ratings ("HIGH confidence on X...
// MODERATE confidence on Y"). buildConfidenceNoteHtml wraps each rating in
// ** markers before the text goes through the site's existing **bold**
// handling. House style (checked against all 769 published notes): the
// rating is UPPERCASE ("HIGH", "MODERATE-HIGH", "VERY HIGH", ...), so
// that's the rule; only sentence-initial "High confidence"-style text is
// also caught. Lowercase prose ("with high confidence until verified") is
// deliberately left alone -- it isn't a rating label.
const boldConfidenceRatings = (0, eval)(`${extractFunction(source, "bold-confidence-ratings")}\nboldConfidenceRatings;`);

test("boldConfidenceRatings bolds a single uppercase rating", () => {
  assert.equal(boldConfidenceRatings("HIGH confidence on the orders."), "**HIGH** confidence on the orders.");
});

test("boldConfidenceRatings bolds every rating when a note has several", () => {
  assert.equal(
    boldConfidenceRatings("HIGH confidence on the orders. MODERATE confidence on the cost. LOW confidence on intent."),
    "**HIGH** confidence on the orders. **MODERATE** confidence on the cost. **LOW** confidence on intent."
  );
});

test("boldConfidenceRatings keeps combined ratings together as one span", () => {
  assert.equal(boldConfidenceRatings("MODERATE-HIGH confidence on X"), "**MODERATE-HIGH** confidence on X");
  assert.equal(boldConfidenceRatings("LOW-MODERATE confidence on X"), "**LOW-MODERATE** confidence on X");
  assert.equal(boldConfidenceRatings("MODERATE-LOW confidence on X"), "**MODERATE-LOW** confidence on X");
  assert.equal(boldConfidenceRatings("MODERATE/HIGH confidence on X"), "**MODERATE/HIGH** confidence on X");
  assert.equal(boldConfidenceRatings("VERY HIGH confidence -- this is"), "**VERY HIGH** confidence -- this is");
});

test("boldConfidenceRatings bolds only the rating in attributive and qualified forms", () => {
  assert.equal(boldConfidenceRatings("the entry's HIGH-confidence sourcing"), "the entry's **HIGH**-confidence sourcing");
  assert.equal(boldConfidenceRatings("MODERATE/contested confidence on X"), "**MODERATE**/contested confidence on X");
  assert.equal(boldConfidenceRatings("raised from MODERATE-to-HIGH confidence"), "raised from **MODERATE**-to-**HIGH** confidence");
});

test("boldConfidenceRatings bolds ratings that aren't followed by the word confidence", () => {
  assert.equal(boldConfidenceRatings("flagged MODERATE pending a primary source"), "flagged **MODERATE** pending a primary source");
  assert.equal(boldConfidenceRatings("MODERATE rather than HIGH confidence"), "**MODERATE** rather than **HIGH** confidence");
});

test("boldConfidenceRatings catches a sentence-initial capitalized rating followed by confidence", () => {
  assert.equal(boldConfidenceRatings("High confidence throughout."), "**High** confidence throughout.");
  assert.equal(boldConfidenceRatings("Moderate confidence on downstream impact."), "**Moderate** confidence on downstream impact.");
});

test("boldConfidenceRatings leaves lowercase prose and non-rating words alone", () => {
  const untouched = [
    "cannot name a specific individual with high confidence until verified",
    "supports moderate-high rather than low confidence",
    "High stakes for rural hospitals",
    "Low-income families are affected",
    "HIGHLY corroborated; LOWER estimate; MODERATED tone",
  ];
  for (const text of untouched) assert.equal(boldConfidenceRatings(text), text, `should not change: ${text}`);
});

test("boldConfidenceRatings does not touch text already inside a ** span, and is idempotent", () => {
  assert.equal(
    boldConfidenceRatings("**HIGH confidence** on X. MODERATE confidence on Y."),
    "**HIGH confidence** on X. **MODERATE** confidence on Y."
  );
  const once = boldConfidenceRatings("HIGH confidence on X. MODERATE-HIGH confidence on Y.");
  assert.equal(boldConfidenceRatings(once), once, "a second pass must not double-bold");
});

test("boldConfidenceRatings returns an empty string for missing text", () => {
  assert.equal(boldConfidenceRatings(""), "");
  assert.equal(boldConfidenceRatings(undefined), "");
  assert.equal(boldConfidenceRatings(null), "");
});

const ratingNote = "HIGH confidence on the order. MODERATE-HIGH confidence on the cost. Update 2026-08-02: LOW confidence on intent.";
for (const [kind, extra] of [
  ["deregulation", { what_changed: "x", estimated_health_impact: {}, primary_proponent: { name: "A", role: "B" }, sources: [] }],
  ["govservices", { institution: "I", what_changed: "x", estimated_impact: {}, primary_proponent: { name: "A", role: "B" }, sources: [] }],
  ["prosecution", { offense_category: "Fraud", status_category: "Investigation", incident_summary: "s", status: "t" }],
]) {
  test(`${kind} Confidence note bolds ratings in the main text and in the dated updates`, () => {
    const result = buildDetailHtml({ ...extra, confidence_note: ratingNote }, { kind });
    assert(result.includes("<strong>HIGH</strong> confidence on the order"), "main-text rating should be bold");
    assert(result.includes("<strong>MODERATE-HIGH</strong> confidence on the cost"), "combined rating should be one bold span");
    assert(result.includes("<strong>LOW</strong> confidence on intent"), "a rating inside a dated update should be bold too");
  });
}

test("the one-line Confidence summary is left as it was (already fully bold), not run through rating-bolding", () => {
  const entry = {
    what_changed: "x", estimated_health_impact: {}, primary_proponent: { name: "A", role: "B" }, sources: [],
    confidence_note: "HIGH confidence on X.",
    section_summaries: { what_changed: "a", estimated_impact: "b", confidence_note: "HIGH overall." },
  };
  const result = buildDetailHtml(entry, { kind: "deregulation" });
  assert(result.includes('<p class="field-summary">HIGH overall.</p>'), "summary line should not gain a nested <strong>");
});

test("a search term that matches a bolded rating still highlights inside the bold", () => {
  const entry = {
    what_changed: "x", estimated_health_impact: {}, primary_proponent: { name: "A", role: "B" }, sources: [],
    confidence_note: "HIGH confidence on X.",
  };
  const result = buildDetailHtml(entry, { kind: "deregulation" }, "high", false);
  assert(result.includes('<strong><mark class="hl">HIGH</mark></strong>'), "search mark should nest cleanly inside the rating's bold");
});

test("a Confidence note with no ratings renders unchanged", () => {
  const entry = {
    what_changed: "x", estimated_health_impact: {}, primary_proponent: { name: "A", role: "B" }, sources: [],
    confidence_note: "Sourced to two outlets; no dispute identified.",
  };
  const result = buildDetailHtml(entry, { kind: "deregulation" });
  assert(result.includes("<p>Sourced to two outlets; no dispute identified.</p>"), "text without a rating passes through untouched");
});

// ---- Bold the leading sourcing-quality phrase (2026-09-19) ------------
// ~140 notes (mostly Deregulation and Government Service) open with a
// sourcing-quality phrase ("Strong sourcing on...", "Very strong...",
// "Well-corroborated across...") instead of a HIGH/MODERATE rating. Those
// describe how solid the entry's SOURCES are, not a per-claim confidence,
// so they are bolded for visual consistency but never rewritten into a
// rating. Only at the very start of the base text; only the quality words
// themselves (not the noun after them), matching how ratings are bolded.
const boldLeadingSourcingQuality = (0, eval)(`${extractFunction(source, "bold-leading-sourcing-quality")}\nboldLeadingSourcingQuality;`);

test("boldLeadingSourcingQuality bolds the leading quality words, not the noun after them", () => {
  const cases = [
    ["Strong sourcing on the waiver.", "**Strong** sourcing on the waiver."],
    ["Very strong sourcing: court filings are primary.", "**Very strong** sourcing: court filings are primary."],
    ["Exceptionally strong sourcing across outlets.", "**Exceptionally strong** sourcing across outlets."],
    ["Unusually strong entry, similar to X.", "**Unusually strong** entry, similar to X."],
    ["Extremely well-documented from many angles.", "**Extremely well-documented** from many angles."],
    ["Well-corroborated across multiple outlets.", "**Well-corroborated** across multiple outlets."],
    ["Well documented across specialist outlets.", "**Well documented** across specialist outlets."],
    ["Solid on the facts of the action.", "**Solid** on the facts of the action."],
    ["Strong, multi-source documentation.", "**Strong**, multi-source documentation."],
    ["Strongly sourced: a primary-source coalition.", "**Strongly sourced**: a primary-source coalition."],
    ["Extensively corroborated by independent outlets.", "**Extensively corroborated** by independent outlets."],
    ["Very strongly sourced across outlets.", "**Very strongly sourced** across outlets."],
  ];
  for (const [input, expected] of cases) assert.equal(boldLeadingSourcingQuality(input), expected, input);
});

test("boldLeadingSourcingQuality only acts at the very start of the text", () => {
  const untouched = [
    "The sourcing here is strong and solid.",
    "Sourced primarily to one outlet; strong on the facts.",
    "Corroborated across multiple independent outlets.",
    "This is legislation, not a rule.",
    "Strongly worded criticism from the opposition.",
    "Extensively reported on by the trade press.",
    "The claim is strongly sourced and extensively corroborated.",
    "HIGH confidence on the orders; strong sourcing overall.",
  ];
  for (const text of untouched) assert.equal(boldLeadingSourcingQuality(text), text, text);
});

test("boldLeadingSourcingQuality leaves already-bold text alone and is idempotent", () => {
  assert.equal(boldLeadingSourcingQuality("**Strong sourcing** on X."), "**Strong sourcing** on X.");
  const once = boldLeadingSourcingQuality("Very strong sourcing on X.");
  assert.equal(boldLeadingSourcingQuality(once), once);
});

test("boldLeadingSourcingQuality returns an empty string for missing text", () => {
  assert.equal(boldLeadingSourcingQuality(""), "");
  assert.equal(boldLeadingSourcingQuality(undefined), "");
});

test("Confidence note bolds a leading sourcing-quality phrase alongside ratings, but not inside a dated update", () => {
  const entry = {
    what_changed: "x", estimated_health_impact: {}, primary_proponent: { name: "A", role: "B" }, sources: [],
    confidence_note: "Strong sourcing on the order. MODERATE confidence on intent. Update 2026-08-02: Strong sourcing on the follow-up.",
  };
  const result = buildDetailHtml(entry, { kind: "deregulation" });
  assert(result.includes("<strong>Strong</strong> sourcing on the order"), "leading quality phrase should be bold");
  assert(result.includes("<strong>MODERATE</strong> confidence on intent"), "rating should still be bold");
  assert(result.includes("Update 2026-08-02: Strong sourcing on the follow-up"), "an update's own text is not treated as a note opening");
  assert.equal((result.match(/<strong>Strong<\/strong>/g) || []).length, 1, "only the note's opening is bolded");
});

test("a note that opens with a rating gets no extra opening bold", () => {
  const entry = {
    what_changed: "x", estimated_health_impact: {}, primary_proponent: { name: "A", role: "B" }, sources: [],
    confidence_note: "HIGH confidence on the order.",
  };
  const result = buildDetailHtml(entry, { kind: "deregulation" });
  assert(result.includes("<p><strong>HIGH</strong> confidence on the order.</p>"), "just the rating is bold in the note paragraph, nothing extra");
});

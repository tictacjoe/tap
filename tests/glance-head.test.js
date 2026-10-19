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
  extractFunction(source, "glance-head");
const api = (0, eval)(
  `${combined}\n({ isValidGlance, glanceActive, buildGlanceHeadHtml, glanceDetailTitleHtml, highlightMatches, violationConcernValue });`
);

const hlPlain = (text) => api.highlightMatches(text || "", "", false);

function validGlance(overrides = {}) {
  return {
    who: "Example Agency Administrator",
    what: "Rolled back an example safety rule with no replacement",
    harm: { kind: "rights", certainty: "alleged", who: "Example detainees" },
    reviewed: "2026-09-20",
    ...overrides,
  };
}
const cfgOn = { kind: "prosecution", titleField: "official", glanceEnabled: true };
const cfgOff = { kind: "prosecution", titleField: "official", glanceEnabled: false };

test("isValidGlance accepts a well-formed block", () => {
  assert.equal(api.isValidGlance(validGlance()), true);
});

test("isValidGlance rejects missing, oversized, multiline and mis-typed fields", () => {
  assert.equal(api.isValidGlance(null), false);
  assert.equal(api.isValidGlance({}), false);
  assert.equal(api.isValidGlance(validGlance({ who: "" })), false);
  assert.equal(api.isValidGlance(validGlance({ who: "x".repeat(51) })), false);
  assert.equal(api.isValidGlance(validGlance({ what: "x".repeat(111) })), false);
  assert.equal(api.isValidGlance(validGlance({ what: "a\nb" })), false);
  assert.equal(api.isValidGlance(validGlance({ harm: { kind: "vibes", certainty: "alleged", who: "X" } })), false);
  assert.equal(api.isValidGlance(validGlance({ harm: { kind: "money", certainty: "probably", who: "X" } })), false);
  assert.equal(api.isValidGlance(validGlance({ harm: { kind: "money", certainty: "alleged", who: "x".repeat(41) } })), false);
  assert.equal(api.isValidGlance(validGlance({ harm: null })), false);
});

test("glanceActive needs the tracker flag AND a valid block", () => {
  assert.equal(api.glanceActive({ glance: validGlance() }, cfgOn), true);
  assert.equal(api.glanceActive({ glance: validGlance() }, cfgOff), false);
  assert.equal(api.glanceActive({ glance: { who: "" } }, cfgOn), false);
  assert.equal(api.glanceActive({}, cfgOn), false);
});

test("buildGlanceHeadHtml returns null when glance is not active", () => {
  assert.equal(api.buildGlanceHeadHtml({ glance: validGlance() }, cfgOff, { hl: hlPlain }), null);
  assert.equal(api.buildGlanceHeadHtml({}, cfgOn, { hl: hlPlain }), null);
});

test("buildGlanceHeadHtml renders who, what, Harm to and harm status, with no Harm type badge", () => {
  const html = api.buildGlanceHeadHtml({ glance: validGlance() }, cfgOn, { hl: hlPlain });
  assert.ok(html.startsWith('<div class="entry-head">'));
  assert.ok(html.includes('<span class="glance-who">Example Agency Administrator</span> — Rolled back'));
  assert.ok(html.includes(">Harm to:</span> <span class=\"glance-harm-who\">Example detainees</span>"));
  assert.ok(html.includes(">Harm status:</span> alleged"));
  assert.ok(!html.includes("Harm type"));
  assert.ok(!html.includes("glance-badge"));
  assert.ok(!html.includes("was harmed"));
});

test("Harm to leads the harm line, then Harm status, then Principal", () => {
  const html = api.buildGlanceHeadHtml({ glance: validGlance() }, cfgOn, { hl: hlPlain });
  assert.ok(html.includes(">Principal:</span> Example Agency Administrator"));
  const line = html.slice(html.indexOf('<p class="glance-harm">'));
  assert.ok(line.startsWith('<p class="glance-harm"><span class="glance-harm-item"><span class="glance-harm-label glance-harm-label-harmed">Harm to:</span>'),
    "Harm to should be the first item on the line");
  const harmToIdx = html.indexOf("Harm to:");
  const statusIdx = html.indexOf("Harm status:");
  const principalIdx = html.indexOf("Principal:");
  assert.ok(harmToIdx < statusIdx, "Harm status should come after Harm to");
  assert.ok(statusIdx < principalIdx, "Principal should come after Harm status");
});

test("Principal still renders when hideWho hides the title's who-lead-in", () => {
  const html = api.buildGlanceHeadHtml({ glance: validGlance() }, cfgOn, { hl: hlPlain, hideWho: true });
  assert.ok(!html.includes("glance-who"), "the title lead-in should still be gone");
  assert.ok(html.includes(">Principal:</span> Example Agency Administrator"), "but the name should still appear via Principal");
});

test("Principal renders for non-Cabinet-Level trackers too (no cfg.kind guard, unlike Violation/Concern Type)", () => {
  const cfgDeregulation = { kind: "deregulation", titleField: "rule_name", glanceEnabled: true };
  const html = api.buildGlanceHeadHtml({ glance: validGlance() }, cfgDeregulation, { hl: hlPlain });
  assert.ok(html.includes(">Principal:</span> Example Agency Administrator"));
});

test("Cabinet-Level: Violation/Concern Type and Status Stage render after Principal", () => {
  const entry = {
    glance: validGlance(),
    offense_category: "Fraud",
    status_category: "Investigation",
  };
  const html = api.buildGlanceHeadHtml(entry, cfgOn, { hl: hlPlain });
  assert.ok(html.includes(">Violation/Concern Type:</span> Fraud"));
  assert.ok(html.includes(">Status Stage:</span> Investigation"));
  const principalIdx = html.indexOf("Principal:");
  const violationIdx = html.indexOf("Violation/Concern Type:");
  const statusIdx = html.indexOf("Status Stage:");
  assert.ok(principalIdx < violationIdx, "Violation/Concern Type should come after Principal");
  assert.ok(violationIdx < statusIdx, "Status Stage should come after Violation/Concern Type");
});

test("Cabinet-Level: the concern caveat still renders in the glance line when it's a concern, not a violation", () => {
  const entry = {
    glance: validGlance(),
    offense_category: "Other/Unclassified",
    concern_type: "Norms/Institutional Erosion",
    status_category: "Ongoing",
  };
  const html = api.buildGlanceHeadHtml(entry, cfgOn, { hl: hlPlain });
  assert.ok(html.includes(">Violation/Concern Type:</span> Norms/Institutional Erosion <em>(not alleged as a legal violation)</em>"));
});

test("non-Cabinet-Level trackers don't get the Violation/Concern Type or Status Stage spans", () => {
  const cfgDeregulation = { kind: "deregulation", titleField: "rule_name", glanceEnabled: true };
  const entry = { glance: validGlance(), offense_category: "Fraud", status_category: "Investigation" };
  const html = api.buildGlanceHeadHtml(entry, cfgDeregulation, { hl: hlPlain });
  assert.ok(!html.includes("Violation/Concern Type"));
  assert.ok(!html.includes("Status Stage"));
});

test("the environment harm kind is accepted and renders a place as Harm to", () => {
  const glance = validGlance({
    harm: { kind: "environment", certainty: "projected", who: "Arctic Refuge coastal plain" },
  });
  assert.equal(api.isValidGlance(glance), true);
  const html = api.buildGlanceHeadHtml({ glance }, cfgOn, { hl: hlPlain });
  assert.ok(html.includes(">Harm to:</span> <span class=\"glance-harm-who\">Arctic Refuge coastal plain</span>"));
  assert.ok(html.includes(">Harm status:</span> projected"));
});

test("the averted certainty is accepted and renders as its Harm status", () => {
  const glance = validGlance({
    harm: { kind: "physical", certainty: "averted", who: "People breathing fine-particle soot" },
  });
  assert.equal(api.isValidGlance(glance), true);
  const html = api.buildGlanceHeadHtml({ glance }, cfgOn, { hl: hlPlain });
  assert.ok(html.includes(">Harm to:</span> <span class=\"glance-harm-who\">People breathing fine-particle soot</span>"));
  assert.ok(html.includes(">Harm status:</span> averted"));
});

test("hideWho drops the responsible-party lead-in but keeps the what line", () => {
  const html = api.buildGlanceHeadHtml({ glance: validGlance() }, cfgOn, { hl: hlPlain, hideWho: true });
  assert.ok(!html.includes("glance-who"));
  assert.ok(html.includes("Rolled back an example safety rule"));
});

test("metaHtml and shareBtnHtml are included", () => {
  const html = api.buildGlanceHeadHtml({ glance: validGlance() }, cfgOn, {
    hl: hlPlain, metaHtml: "<span>META</span>", shareBtnHtml: " <button>SHARE</button>",
  });
  assert.ok(html.includes('<div class="entry-meta"><span>META</span></div>'));
  assert.ok(html.includes("<button>SHARE</button>"));
});

test("text fields are HTML-escaped", () => {
  const html = api.buildGlanceHeadHtml(
    { glance: validGlance({ who: "<b>Bad</b>" }) }, cfgOn, { hl: hlPlain });
  assert.ok(html.includes("&lt;b&gt;Bad&lt;/b&gt;"));
  assert.ok(!html.includes("<b>Bad</b>"));
});

test("search terms are highlighted in the what line", () => {
  const hl = (text) => api.highlightMatches(text || "", "safety", false);
  const html = api.buildGlanceHeadHtml({ glance: validGlance() }, cfgOn, { hl });
  assert.ok(html.includes('<mark class="hl">safety</mark>'));
});

test("glanceDetailTitleHtml puts the original title back as the Details heading", () => {
  const entry = { official: "Jane Example, Secretary of Example", glance: validGlance() };
  assert.equal(
    api.glanceDetailTitleHtml(entry, cfgOn, hlPlain),
    '<p class="glance-orig-title">Jane Example, Secretary of Example</p>'
  );
  assert.equal(api.glanceDetailTitleHtml(entry, cfgOff, hlPlain), "");
});

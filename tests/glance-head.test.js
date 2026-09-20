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
  extractFunction(source, "glance-head");
const api = (0, eval)(
  `${combined}\n({ isValidGlance, glanceActive, buildGlanceHeadHtml, glanceDetailTitleHtml, highlightMatches });`
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

test("buildGlanceHeadHtml renders who, what, the harm badge and harm who", () => {
  const html = api.buildGlanceHeadHtml({ glance: validGlance() }, cfgOn, { hl: hlPlain });
  assert.ok(html.startsWith('<div class="entry-head">'));
  assert.ok(html.includes('<span class="glance-who">Example Agency Administrator</span> — Rolled back'));
  assert.ok(html.includes("glance-badge-rights"));
  assert.ok(html.includes("Rights &amp; liberty · alleged"));
  assert.ok(html.includes("Example detainees"));
});

test("the environment harm kind is accepted and renders its own badge class and label", () => {
  const glance = validGlance({
    harm: { kind: "environment", certainty: "projected", who: "Arctic Refuge coastal plain" },
  });
  assert.equal(api.isValidGlance(glance), true);
  const html = api.buildGlanceHeadHtml({ glance }, cfgOn, { hl: hlPlain });
  assert.ok(html.includes("glance-badge-environment"));
  assert.ok(html.includes("Environment · projected"));
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

// Front-page findings strip (2026-11-23, spec tap-data
// docs/superpowers/specs/2026-11-23-front-strip-design.md): the pure
// builder that turns data/front-strip.json into the strip's HTML.
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
  extractFunction(source, "front-strip");
const { buildFrontStripHtml } = (0, eval)(`${combined}\n({ buildFrontStripHtml });`);

const color = key => `var(--trk-${key})`;

function strip(featured) {
  return {
    as_of: "2026-11-23",
    stats: { entries: 1234, life_health: 118, illegality: 274, claim_checks: 308 },
    featured: featured === undefined ? {
      tracker: "govservices", id: "niosh-cuts", label: "Government Service Redirection",
      what: 'Cut <b>aid</b> & "more"', who: "9/11 responders", status: "Court ruled",
      pull_quote: "Specimens were left.", certainty: "documented", since: "2026-11-23",
    } : featured,
    history: [],
  };
}

test("renders four stats in order", () => {
  const html = buildFrontStripHtml(strip(), color);
  const labels = [...html.matchAll(/class="fs-label">([^<]*)</g)].map(m => m[1]);
  assert.deepEqual(labels, ["sourced entries", "harm life or health", "possible illegality", "claim checks"]);
  const nums = [...html.matchAll(/class="fs-num[^"]*">([^<]*)</g)].map(m => m[1]);
  assert.deepEqual(nums, ["1,234", "118", "274", "308"]);
});

test("renders featured card with escaped text", () => {
  const html = buildFrontStripHtml(strip(), color);
  assert.ok(html.includes("Cut &lt;b&gt;aid&lt;/b&gt; &amp; &quot;more&quot;"));
  assert.ok(!html.includes("<b>aid</b>"));
  assert.ok(html.includes("Harmed: 9/11 responders"));
  assert.ok(html.includes("See all life/health harms →"));
  assert.ok(html.includes("Specimens were left."));
  assert.ok(html.includes("Court ruled"));
  assert.ok(html.includes("var(--trk-govservices)"));
});

test("entry link carries tracker and id", () => {
  const html = buildFrontStripHtml(strip(), color);
  assert.match(html, /<a [^>]*class="fs-entry-link"[^>]*data-tracker="govservices"[^>]*data-id="niosh-cuts"/);
  assert.match(html, /class="fs-harms-link"/);
  assert.match(html, /<button [^>]*class="fs-toggle"[^>]*aria-expanded="false"/);
  assert.match(html, /<button [^>]*aria-controls="fs-card"/);
  assert.match(html, /<div class="fs-card" id="fs-card"/);
  assert.doesNotMatch(html, /<h2/);
});

test("null featured omits card and toggle", () => {
  const html = buildFrontStripHtml(strip(null), color);
  assert.ok(html.includes("front-strip-inner"));
  assert.ok(!html.includes("fs-card"));
  assert.ok(!html.includes("fs-toggle"));
});

test("missing stats returns empty string", () => {
  assert.equal(buildFrontStripHtml({}, color), "");
  assert.equal(buildFrontStripHtml(null, color), "");
});

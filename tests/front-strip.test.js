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

const ILL = {
  tracker: "deregulation", id: "epa-x", label: "Corporate Deregulation",
  what: "Rolled back <rule>", status: "In court", law: "Clean Air Act", cite: "42 U.S.C. 7401",
  law_label: "civil", who: "EPA", why: "A judge found it likely unlawful.", more_laws: 2, since: "2026-11-23",
};

function strip(featured, featuredIll) {
  return {
    as_of: "2026-11-23",
    stats: { entries: 1234, life_health: 118, illegality: 274, reporting: 615 },
    featured_illegality: featuredIll === undefined ? ILL : featuredIll,
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
  assert.deepEqual(labels, ["sourced entries", "harms to life or health", "entries describing possible illegality", "uncurated reporting"]);
  const nums = [...html.matchAll(/class="fs-num[^"]*">([^<]*)</g)].map(m => m[1]);
  assert.deepEqual(nums, ["1,234", "118", "274", "615"]);
  assert.ok(!html.includes("claim checks"));
});

test("first three numbers link to their views, reporting does not", () => {
  const html = buildFrontStripHtml(strip(), color);
  const links = [...html.matchAll(/<a href="([^"]*)" data-goto="([^"]*)"[^>]*class="fs-num fs-num-link[^"]*">([^<]*)</g)]
    .map(m => [m[1], m[2], m[3]]);
  assert.deepEqual(links, [["#", "all", "1,234"], ["#harms", "harms", "118"], ["#illegality", "illegality", "274"]]);
  assert.match(html, /<span class="fs-num">615<\/span>/);
});

test("renders featured possible-illegality card, escaped and hedged", () => {
  const html = buildFrontStripHtml(strip(), color);
  assert.ok(html.includes("Rolled back &lt;rule&gt;"));
  assert.ok(html.includes("May violate: Clean Air Act"));
  assert.ok(html.includes("(42 U.S.C. 7401)"));
  assert.ok(html.includes("(+2 more)"));
  assert.ok(html.includes("By: EPA"));
  assert.ok(html.includes("A judge found it likely unlawful."));
  assert.ok(html.includes("Featured possible illegality · Corporate Deregulation"));
  assert.match(html, /<a [^>]*class="fs-entry-link"[^>]*data-tracker="deregulation"[^>]*data-id="epa-x"/);
  assert.match(html, /class="fs-illegality-link"/);
  assert.match(html, /<button [^>]*aria-controls="fs-card-illegality"/);
  assert.match(html, /<div class="fs-card" id="fs-card-illegality"/);
  // harm card comes first
  assert.ok(html.indexOf("fs-card-harm") < html.indexOf("fs-card-illegality"));
});

test("null illegality feature omits only that card", () => {
  const html = buildFrontStripHtml(strip(undefined, null), color);
  assert.ok(html.includes("fs-card-harm"));
  assert.ok(!html.includes("fs-card-illegality"));
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
  assert.match(html, /<button [^>]*aria-controls="fs-card-harm"/);
  assert.match(html, /<div class="fs-card" id="fs-card-harm"/);
  assert.doesNotMatch(html, /<h2/);
});

test("null featured omits cards and toggles", () => {
  const html = buildFrontStripHtml(strip(null, null), color);
  assert.ok(html.includes("front-strip-inner"));
  assert.ok(!html.includes("fs-card"));
  assert.ok(!html.includes("fs-toggle"));
});

test("missing stats returns empty string", () => {
  assert.equal(buildFrontStripHtml({}, color), "");
  assert.equal(buildFrontStripHtml(null, color), "");
});

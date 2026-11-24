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
  assert.deepEqual(labels, ["curated entries", "harms to life or health", "entries describing possible illegality", "uncurated reporting"]);
  const nums = [...html.matchAll(/class="fs-num[^"]*">([^<]*)</g)].map(m => m[1]);
  assert.deepEqual(nums, ["1,234", "118", "274", "615"]);
  assert.ok(!html.includes("claim checks"));
});

test("all four numbers link to their views", () => {
  const html = buildFrontStripHtml(strip(), color);
  const links = [...html.matchAll(/<a href="([^"]*)" data-goto="([^"]*)"[^>]*class="fs-num fs-num-link[^"]*">([^<]*)</g)]
    .map(m => [m[1], m[2], m[3]]);
  assert.deepEqual(links, [["#", "all", "1,234"], ["#harms", "harms", "118"], ["#illegality", "illegality", "274"], ["#", "reporting", "615"]]);
});

test("featured cards are never rendered (removed 2026-11-24)", () => {
  const html = buildFrontStripHtml(strip(), color);
  assert.ok(html.includes("front-strip-inner"));
  for (const cls of ["fs-card", "fs-toggle", "fs-feature", "fs-entry-link", "fs-harms-link", "fs-illegality-link"]) {
    assert.ok(!html.includes(cls), cls);
  }
});

test("missing stats returns empty string", () => {
  assert.equal(buildFrontStripHtml({}, color), "");
  assert.equal(buildFrontStripHtml(null, color), "");
});

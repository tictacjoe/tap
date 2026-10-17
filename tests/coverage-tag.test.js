const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function extractFunction(source, name) {
  const s = `/* ${name}:start */`, e = `/* ${name}:end */`;
  const a = source.indexOf(s), b = source.indexOf(e);
  if (a === -1 || b === -1) throw new Error(`Markers for ${name} not found in index.html`);
  return source.slice(a + s.length, b);
}
const source = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");

// buildCoverageTagHtml reads the global TRACKERS (through
// isHiddenRelatedTarget and for tracker labels). A mutable global stub
// lets each test flip TRACKERS.trumpfamily.hidden.
globalThis.TRACKERS = {
  trumpfamily: { label: "Trump Family", hidden: true },
  prosecution: { label: "Cabinet-Level Accountability" },
};
const buildCoverageTagHtml = (0, eval)(
  ["escape-html", "related-tracker-field-to-key", "build-coverage-tag-html"]
    .map(n => extractFunction(source, n)).join("\n") + "\nbuildCoverageTagHtml;");

test("promoted_to a hidden tracker renders no tag; visible renders the In link", () => {
  TRACKERS.trumpfamily.hidden = true;
  assert.equal(buildCoverageTagHtml({ promoted_to: "trumpfamily/m1" }), "");
  TRACKERS.trumpfamily.hidden = false;
  const html = buildCoverageTagHtml({ promoted_to: "trumpfamily/m1" });
  assert.match(html, /^<a /);
  assert.match(html, /In Trump Family/);
  assert.match(html, /data-id="m1"/);
  TRACKERS.trumpfamily.hidden = true;
});

test("related_entries skip a hidden tracker and link the first visible one", () => {
  TRACKERS.trumpfamily.hidden = true;
  const html = buildCoverageTagHtml({ related_entries: [{ tracker: "trumpfamily", id: "m1" }, { tracker: "prosecution", id: "p1" }] });
  assert.match(html, /Also in Cabinet-Level Accountability/);
  assert.match(html, /data-tracker="prosecution" data-id="p1"/);
});

test("no promoted_to or related_entries -> empty", () => {
  assert.equal(buildCoverageTagHtml({}), "");
});

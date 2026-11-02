const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function extractRegion(source, name) {
  const startMarker = `/* ${name}:start */`;
  const endMarker = `/* ${name}:end */`;
  const start = source.indexOf(startMarker);
  const end = source.indexOf(endMarker);
  if (start === -1 || end === -1) throw new Error(`Markers for ${name} not found in index.html`);
  return source.slice(start + startMarker.length, end);
}

const source = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");
const { TRACKER_COLORS, trackerChipHtml } = (0, eval)(
  extractRegion(source, "tracker-colors") + "\n({ TRACKER_COLORS, trackerChipHtml });"
);

const EXPECTED = {
  prosecution: "#7a3f8f",
  govservices: "#00846a",
  deregulation: "#b0561a",
  dai: "#3462b0",
  trumpfamily: "#a3303f",
  oea: "#8a7a0a",
};

test("TRACKER_COLORS holds the six exact colors", () => {
  assert.deepEqual(TRACKER_COLORS, EXPECTED);
});

test(":root declares each --trk-<key> with the exact hex", () => {
  for (const [key, hex] of Object.entries(EXPECTED)) {
    assert.match(source, new RegExp(`--trk-${key}:\\s*${hex}\\s*;`, "i"), key);
  }
});

test("trackerChipHtml is empty for non-curated or unknown keys", () => {
  for (const k of ["tracker", "communitytopics", "nope", ""]) assert.equal(trackerChipHtml(k), "");
});

test("trackerChipHtml carries the color var and the tracker name as text", () => {
  const html = trackerChipHtml("dai");
  assert.ok(html.includes("var(--trk-dai)"));
  assert.ok(html.includes("tracker-chip"));
  assert.ok(html.includes("DHS and ICE"));
});

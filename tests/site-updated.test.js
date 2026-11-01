const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

// Pull formatSiteUpdated out of index.html between its marker comments.
const source = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");
const start = source.indexOf("/* site-updated:start */");
const end = source.indexOf("/* site-updated:end */");
if (start === -1 || end === -1) throw new Error("site-updated markers not found in index.html");
const { formatSiteUpdated } = (0, eval)(
  source.slice(start, end) + "\n({ formatSiteUpdated });"
);

test("formats an ISO date as Updated Mon D, YYYY", () => {
  assert.equal(formatSiteUpdated("2026-11-01"), "Updated Nov 1, 2026");
  assert.equal(formatSiteUpdated("2026-12-25"), "Updated Dec 25, 2026");
});

test("returns empty string for missing or unparseable input", () => {
  assert.equal(formatSiteUpdated(undefined), "");
  assert.equal(formatSiteUpdated(null), "");
  assert.equal(formatSiteUpdated("garbage"), "");
  assert.equal(formatSiteUpdated("2026-13-45"), "");
});

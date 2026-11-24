const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

// Pull withLoadCount out of index.html between its marker comments
// (same technique as site-updated.test.js).
const source = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");
const start = source.indexOf("/* reporting-load-labels:start */");
const end = source.indexOf("/* reporting-load-labels:end */");
if (start === -1 || end === -1) throw new Error("reporting-load-labels markers not found in index.html");
const { withLoadCount } = (0, eval)(
  source.slice(start, end) + "\n({ withLoadCount });"
);

test("appends the count once loaded, including zero", () => {
  assert.equal(withLoadCount("Uncurated reporting", 812), "Uncurated reporting (812)");
  assert.equal(withLoadCount("Uncurated reporting", 0), "Uncurated reporting (0)");
});

test("shows loading while the count is unknown", () => {
  assert.equal(withLoadCount("Uncurated reporting", null), "Uncurated reporting (loading…)");
  assert.equal(withLoadCount("Uncurated reporting", undefined), "Uncurated reporting (loading…)");
});

test("shows unavailable when the load failed", () => {
  assert.equal(withLoadCount("Uncurated reporting", null, true), "Uncurated reporting (unavailable)");
});

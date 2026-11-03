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

// Pull in the marker blocks the key-events renderer depends on, then
// expose the functions under test.
const harness = new Function(
  extractFunction(source, "escape-html") +
  extractFunction(source, "format-key-event-date") +
  "return { escapeHtml, formatKeyEventDate };"
)();
const { formatKeyEventDate } = harness;

test("formatKeyEventDate: first event shows full date with year", () => {
  assert.equal(formatKeyEventDate("2026-07-03", null), "Jul 3, 2026");
});

test("formatKeyEventDate: same year as previous drops the year", () => {
  assert.equal(formatKeyEventDate("2026-10-22", "2026-08-18"), "Oct 22");
});

test("formatKeyEventDate: year change shows the year", () => {
  assert.equal(formatKeyEventDate("2027-01-05", "2026-12-30"), "Jan 5, 2027");
});

test("formatKeyEventDate: month precision is Mon YYYY", () => {
  assert.equal(formatKeyEventDate("2026-10", "2026-09-01"), "Oct 2026");
});

test("formatKeyEventDate: year precision is YYYY", () => {
  assert.equal(formatKeyEventDate("2026", null), "2026");
});

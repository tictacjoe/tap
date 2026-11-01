const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function extractFunction(source, name) {
  const startMarker = `/* ${name}:start */`;
  const endMarker = `/* ${name}:end */`;
  const start = source.indexOf(startMarker);
  const end = source.indexOf(endMarker);
  if (start === -1 || end === -1) throw new Error(`Markers for ${name} not found in index.html`);
  return source.slice(start + startMarker.length, end);
}

const source = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");
const { headlineSortDate, futureSafeDate, todayDateNum } = (0, eval)(
  `${extractFunction(source, "extract-first-date")}\n${extractFunction(source, "headline-sort-date")}\n({ headlineSortDate, futureSafeDate, todayDateNum });`
);

const TODAY = 20261101;

test("headlineSortDate keeps an ordinary past event date", () => {
  const item = { date: "2026-10-20", trail: { dateAdded: "2026-10-28" } };
  assert.equal(headlineSortDate(item, TODAY), "2026-10-20");
});

test("headlineSortDate falls back to date added when the event date is in the future", () => {
  // The real case (epa-public-web-archive-shutdown-2026): the only ISO date in
  // date_of_action is the planned retirement, so it sorted above today's news.
  const item = {
    date: "2026 (retirement date posted on the archive's homepage a few weeks before Oct. 23, 2026, per Mother Jones); planned retirement 2026-12-31",
    trail: { dateAdded: "2026-10-28" },
  };
  assert.equal(headlineSortDate(item, TODAY), "2026-10-28");
});

test("headlineSortDate keeps today's date (today is not the future)", () => {
  const item = { date: "2026-11-01", trail: { dateAdded: "2026-10-28" } };
  assert.equal(headlineSortDate(item, TODAY), "2026-11-01");
});

test("headlineSortDate keeps a future date when there is no date added to fall back on", () => {
  assert.equal(headlineSortDate({ date: "2026-12-31", trail: {} }, TODAY), "2026-12-31");
  assert.equal(headlineSortDate({ date: "2026-12-31" }, TODAY), "2026-12-31");
});

// Tracker tabs (Service Cuts' default order, every curated tab's "Most recent
// activity") sort raw entries, so they use the same rule on the entry's own
// date_of_action / date_added fields.
test("futureSafeDate swaps a future event date for the date added", () => {
  assert.equal(futureSafeDate("planned retirement 2026-12-31", "2026-10-28", TODAY), "2026-10-28");
  assert.equal(futureSafeDate("2026-10-20", "2026-10-28", TODAY), "2026-10-20");
  assert.equal(futureSafeDate("2026-12-31", null, TODAY), "2026-12-31");
});

test("todayDateNum is the local date in extractFirstDate's YYYYMMDD form", () => {
  assert.equal(todayDateNum(new Date(2026, 10, 1, 23, 59)), 20261101);
  assert.equal(todayDateNum(new Date(2027, 0, 9)), 20270109);
});

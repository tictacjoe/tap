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
const compareByLastVerified = (0, eval)(`${extractFunction(source, "verified-sort")}\ncompareByLastVerified;`);

test("compareByLastVerified puts the most recently verified entry first", () => {
  const rows = [
    { id: "old", last_verified: "2026-07-03" },
    { id: "new", last_verified: "2026-09-19" },
    { id: "mid", last_verified: "2026-08-18" },
  ];
  assert.deepEqual(rows.sort(compareByLastVerified).map(r => r.id), ["new", "mid", "old"]);
});

test("compareByLastVerified sorts an entry with no date last", () => {
  const rows = [{ id: "none" }, { id: "blank", last_verified: "" }, { id: "dated", last_verified: "2026-08-01" }];
  assert.equal(rows.sort(compareByLastVerified)[0].id, "dated");
});

test("compareByLastVerified keeps same-date entries in their existing order (stable)", () => {
  const rows = [
    { id: "a", last_verified: "2026-09-01" },
    { id: "b", last_verified: "2026-09-19" },
    { id: "c", last_verified: "2026-09-01" },
    { id: "d", last_verified: "2026-09-19" },
  ];
  assert.deepEqual(rows.sort(compareByLastVerified).map(r => r.id), ["b", "d", "a", "c"]);
});

test("the sort dropdown offers the option for the three curated trackers only", () => {
  // renderSortToggle is DOM-bound, so check its source line rather than run it.
  assert(source.includes(`if (cfg.kind !== "tracker") options.push(['verified', 'Last verified, newest first']);`));
});

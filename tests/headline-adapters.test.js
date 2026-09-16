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

const indexHtmlPath = path.join(__dirname, "..", "index.html");
const source = fs.readFileSync(indexHtmlPath, "utf8");

const names = [
  "truncate",
  "verdict-label",
  "combine-tier-text",
  "usable-tier-count",
  "adapt-deregulation-entry",
  "adapt-govservices-entry",
  "adapt-prosecution-entry",
  "adapt-communitytopic-entry",
  "adapt-reporting-entry",
];
const combined = names.map(n => extractFunction(source, n)).join("\n");
const exposeNames = [
  "combineTierText", "usableTierCount",
  "adaptDeregulationEntry", "adaptGovServicesEntry", "adaptProsecutionEntry",
  "adaptCommunityTopicEntry", "adaptReportingEntry",
];
const fns = (0, eval)(`${combined}\n({ ${exposeNames.join(", ")} });`);

test("combineTierText joins only non-empty parts with a space", () => {
  assert.equal(fns.combineTierText(["a", "", null, "b"]), "a b");
  assert.equal(fns.combineTierText(["", null, undefined]), "");
});

test("usableTierCount counts leading non-empty, non-duplicate tiers", () => {
  assert.equal(fns.usableTierCount(["a", "a b", "a b c"]), 3);
  assert.equal(fns.usableTierCount(["a", "a", "a"]), 1);
  assert.equal(fns.usableTierCount(["a", "a b", "a b"]), 2);
  assert.equal(fns.usableTierCount(["", "x", "y"]), 0);
});

#!/usr/bin/env node
// cla_concern_ids.js <tap-data-root>
//
// Prints a JSON array of Cabinet-Level (CLA) entry ids that the site shows as a
// "concern" (not alleged as a legal violation). The "Possible Illegality" gate in
// tap-data must never list such an entry, and the classifier lives only in
// index.html, so this script borrows it from there.
//
// Rule (mirrors violationConcernValue() in index.html): an entry is concern-only
// when classifyOffenseCategory(raw) === "Other/Unclassified" AND
// classifyConcernType(raw) !== "Other/Unclassified".
const fs = require("node:fs");
const path = require("node:path");

const OTHER = "Other/Unclassified";

// Pull a function's source out of index.html by brace matching (same approach as
// tests/cla-concern-classification.test.js). index.html is never modified.
function extractByFunctionName(source, name) {
  const m = source.slice(source.indexOf("function " + name));
  let i = m.indexOf("{"), depth = 0, end = -1;
  for (let j = i; j < m.length; j++) {
    if (m[j] === "{") depth++;
    if (m[j] === "}") { depth--; if (depth === 0) { end = j; break; } }
  }
  if (end === -1) throw new Error(`function ${name} not found in index.html`);
  return m.slice(0, end + 1);
}

const source = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");
const classifyOffenseCategory = (0, eval)(`(${extractByFunctionName(source, "classifyOffenseCategory")})`);
const classifyConcernType = (0, eval)(`(${extractByFunctionName(source, "classifyConcernType")})`);

// entries: [{id, offense_category}] -> ids that are concern-only, in input order.
function concernIds(entries) {
  return entries
    .filter((e) => {
      const raw = e.offense_category;
      return classifyOffenseCategory(raw) === OTHER && classifyConcernType(raw) !== OTHER;
    })
    .map((e) => e.id);
}

module.exports = { concernIds };

if (require.main === module) {
  const root = process.argv[2];
  if (!root) {
    console.error("usage: node tools/cla_concern_ids.js <tap-data-root>");
    process.exit(2);
  }
  const dir = path.join(root, "prosecution", "cabinet-level");
  const entries = fs.readdirSync(dir)
    .filter((f) => f.endsWith(".json"))
    .sort()
    .map((f) => JSON.parse(fs.readFileSync(path.join(dir, f), "utf8")));
  console.log(JSON.stringify(concernIds(entries)));
}

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
const regionSource = extractFunction(source, "figure-category");
const { figureCategory, figureKindOf, isFigureSavings } = (0, eval)(
  `${regionSource}\n({ figureCategory, figureKindOf, isFigureSavings });`);

const fig = (metric, value) => ({ metric, value });

test("figureCategory: a dollar value is always Financial regardless of metric text", () => {
  assert.equal(figureCategory(fig("Anything at all", "$8,300,000")), "Financial");
});

test("figureCategory: a metric-only financial keyword (no $ in value) is still Financial", () => {
  assert.equal(figureCategory(fig("Proposed FY2026 budget cut", "10.5%")), "Financial");
});

test("figureCategory: health/safety keywords win over financial ones", () => {
  assert.equal(figureCategory(fig("Workers exposed to hazard pay cuts", "up to 25%")), "Health & safety");
});

test("figureCategory: a plain non-dollar, non-keyword figure is Scale & scope", () => {
  assert.equal(figureCategory(fig("Regional directors serving only in acting capacity", "5 of 10")), "Scale & scope");
});

// The bug this file exists to pin down (found on cisa-cyber-workforce-
// cuts-trump2, 2026-09-23): "funding" appearing only as part of a
// circumstantial "during the ... funding lapse" clause was pulling a
// plain workforce percentage into "Financial".
test("figureCategory: 'during the ... funding lapse' context doesn't make a percentage Financial", () => {
  assert.equal(
    figureCategory(fig("Share of remaining CISA workforce furloughed during the 45-day DHS funding lapse", "~60%")),
    "Scale & scope"
  );
});

test("figureCategory: 'funding halt'/'funding gap'/'funding freeze'/'funding pause' get the same treatment", () => {
  assert.equal(figureCategory(fig("Staff furloughed during the funding halt", "75% of staff")), "Scale & scope");
  assert.equal(figureCategory(fig("Contacts handled amid the funding gap", "~12 million")), "Scale & scope");
  assert.equal(figureCategory(fig("Participants affected by the funding freeze", "10,000+")), "Scale & scope");
  assert.equal(figureCategory(fig("Participants affected by the funding pause", "10,000+")), "Scale & scope");
});

test("figureCategory: 'funding cut'/'budget cut' still count as Financial (not part of the excluded phrase list)", () => {
  assert.equal(figureCategory(fig("Compliance monitoring funding cut", "35%")), "Financial");
  assert.equal(figureCategory(fig("Proposed CDC budget cut", "~50% (halved)")), "Financial");
});

test("figureCategory: a genuine dollar figure inside a funding-lapse metric is still Financial (the $ check runs first)", () => {
  assert.equal(
    figureCategory(fig("Cost of the funding lapse to the agency", "$4,000,000")),
    "Financial"
  );
});

test("figureKindOf follows figureCategory (Scale & scope figures have no harm/savings kind)", () => {
  assert.equal(
    figureKindOf(fig("Share of workforce furloughed during the funding lapse", "~60%")),
    null
  );
});

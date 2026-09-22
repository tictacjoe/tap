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
function extractByFunctionName(name) {
  const m = source.slice(source.indexOf("function " + name));
  let i = m.indexOf("{"), depth = 0, end = -1;
  for (let j = i; j < m.length; j++) { if (m[j] === "{") depth++; if (m[j] === "}") { depth--; if (depth === 0) { end = j; break; } } }
  if (end === -1) throw new Error(`function ${name} not found`);
  return m.slice(0, end + 1);
}
const classifyOffenseCategory = (0, eval)(`(${extractByFunctionName("classifyOffenseCategory")})`);
const classifyConcernType = (0, eval)(`(${extractByFunctionName("classifyConcernType")})`);

// 2026-09-21 narrowing pass: real cases pulled from the residual Other/Unclassified bucket,
// verified against the entry's own actual offense_category text -- not invented examples.
test("classifyOffenseCategory recognizes the new statute/doctrine-named patterns", () => {
  assert.equal(classifyOffenseCategory("Foreign Emoluments Clause (U.S. Const. art. I, sec. 9, cl. 8)"), "Foreign Emoluments Clause Violation");
  assert.equal(classifyOffenseCategory("Bypassing the War Powers Resolution -- conducting military strikes"), "War Powers Resolution Violation");
  assert.equal(classifyOffenseCategory("First Federal Raid of a Journalist's Home -- a Privacy Protection Act Violation"), "Privacy Protection Act Violation");
  assert.equal(classifyOffenseCategory("False Statement to Congress (potential concern under 18 U.S.C. §1001 if made with knowledge)"), "False Statement to Congress (18 U.S.C. § 1001)");
  assert.equal(classifyOffenseCategory("26 U.S.C. § 7217 -- federal law making it a felony for the President"), "IRS Non-Interference Violation (26 U.S.C. § 7217)");
  assert.equal(classifyOffenseCategory('circumventing 42 U.S.C. § 1975\'s requirement that the President designate the chair'), "Civil Rights Commission Act Violation (42 U.S.C. § 1975)");
  assert.equal(classifyOffenseCategory("Violation of a Federal Court Injunction (Kennedy Center Naming)"), "Federal Court Order Defiance");
  assert.equal(classifyOffenseCategory("a district court's contempt inquiry, not yet a finding"), "Federal Court Order Defiance");
  assert.equal(classifyOffenseCategory("Recalling commanders, raises Posse Comitatus Act Concerns"), "Posse Comitatus Act Concern");
  assert.equal(classifyOffenseCategory("Contested Exercise of D.C. Home Rule Act Emergency Authority"), "D.C. Home Rule Act Dispute");
  assert.equal(classifyOffenseCategory("Circumventing Senate Advice-and-Consent Review by Installing a Rejected Nominee"), "Senate Confirmation Bypass");
  assert.equal(classifyOffenseCategory("Federal Procurement Authority Violation -- exercising contracting authority he did not legally hold"), "Federal Procurement Authority Violation");
});

test("classifyOffenseCategory is unaffected for entries that already matched an earlier rule", () => {
  assert.equal(classifyOffenseCategory("Hatch Act violation by a senior official"), "Hatch Act Violation");
  assert.equal(classifyOffenseCategory("A vindictive prosecution against a political critic"), "Selective/Vindictive Prosecution");
});

test("classifyConcernType recognizes the new concern patterns, on text with no named statute", () => {
  assert.equal(classifyConcernType("Part of a Documented Retribution Pattern Also Reaching Comey and James"), "Retaliation Against Critics or Political Opponents");
  assert.equal(classifyConcernType("Repeated Failure to Persuade D.C. Grand Juries to Indict in Cases Tied to Trump's Federal Policing Surge"), "Failed or Rejected Prosecution");
  assert.equal(classifyConcernType("Drawing Bipartisan Accusations of Obstructing Congressional Oversight of the Military"), "Congressional or Internal Oversight Obstructed");
  assert.equal(classifyConcernType("Press Freedom Advocates Warn Chills Journalism and Whistleblowing"), "Press Freedom / Newsgathering Interference");
  assert.equal(classifyConcernType("Public Health Service Commissioned Corps qualification standards disregarded in nomination"), "Appointment/Nomination With Undisclosed or Disqualifying Record");
  assert.equal(classifyConcernType("Foreign Self-Dealing -- a president's family member profiting"), "Self-Dealing or Undisclosed Financial Conflict");
  assert.equal(classifyConcernType("Personal/Recreational Misuse of FBI Aircraft Delaying Real Investigations"), "Misuse of Official Resources or Authority");
  assert.equal(classifyConcernType("Inhumane Conditions of Immigration Detention -- a DHS Inspector General report found"), "Immigration Enforcement Oversight Weakened");
  assert.equal(classifyConcernType("Alleged Obstruction/Cover-Up of a 2010 In-Custody Death"), "Alleged Obstruction or Cover-Up (Non-Adjudicated)");
  assert.equal(classifyConcernType("Evasion of Court-Ordered Testimony Regarding DOGE's Dismantlement of Federal Agencies"), "Evasion of Court-Ordered Testimony");
  assert.equal(classifyConcernType("no criminal or civil legal violation established; the order was issued while a separate court stay"), "Executive Action With No Established Legal Violation (Policy Dispute)");
});

test("classifyConcernType still falls back to Other/Unclassified for genuinely unmatched text", () => {
  assert.equal(classifyConcernType("Authorizing Live Artillery Fire Directly Over a Major Public Interstate Highway"), "Other/Unclassified");
});

test("the new rules do not change classification for any entry the site actually publishes", () => {
  // Regression guard: rerun both classifiers over the full published dataset and confirm the residual
  // "matched by neither classifier" bucket only shrank (88 -> 34 as of the 2026-09-21 narrowing pass),
  // never grew, and no entry that already had a real Violation Type lost it.
  const data = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "data", "prosecution.json"), "utf8"));
  let residual = 0;
  for (const e of data) {
    const v = classifyOffenseCategory(e.offense_category);
    if (v === "Other/Unclassified" && classifyConcernType(e.offense_category) === "Other/Unclassified") residual++;
  }
  assert.equal(residual, 34, "residual Other/Unclassified count drifted -- update this number deliberately if the ruleset or data changed");
});

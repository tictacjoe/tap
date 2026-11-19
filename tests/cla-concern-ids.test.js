// Tests for tools/cla_concern_ids.js: the list of Cabinet-Level entry ids the
// site shows as "not alleged as a legal violation" (concern-only).
const test = require("node:test");
const assert = require("node:assert/strict");
const { concernIds } = require("../tools/cla_concern_ids.js");

test("concernIds keeps only concern-only entries", () => {
  const out = concernIds([
    // Has a real Violation Type (Hatch Act), so it is a violation, not a concern.
    { id: "a", offense_category: "Hatch Act violation by a senior official" },
    // No Violation Type but a concern type matches (string asserted in
    // cla-concern-classification.test.js as "Retaliation Against Critics...").
    { id: "b", offense_category: "Part of a Documented Retribution Pattern Also Reaching Comey and James" },
    // Matches neither classifier, so it is not a concern.
    { id: "c", offense_category: "Authorizing Live Artillery Fire Directly Over a Major Public Interstate Highway" },
  ]);
  assert.deepEqual(out, ["b"]);
});

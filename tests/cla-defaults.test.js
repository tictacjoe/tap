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
const { defaultGroupModeFor, compareByCardTitle } = (0, eval)(
  `${extractFunction(source, "default-group-mode")}\n${extractFunction(source, "glance-head")}\n${extractFunction(source, "alpha-sort")}\n({ defaultGroupModeFor, compareByCardTitle });`
);

test("every tracker, Cabinet-Level included, defaults to flat individual cards", () => {
  for (const key of ["prosecution", "deregulation", "govservices", "tracker", "communitytopics", "headlines"]) {
    assert.equal(defaultGroupModeFor(key), "", key);
  }
});

const cfg = { titleField: "official", idField: "id", glanceEnabled: true };
const glance = (who, what = "did a thing") => ({ who, what, harm: { kind: "money", certainty: "alleged", who: "taxpayers" } });

test("compareByCardTitle sorts A to Z by the glance name the card leads with, not by `official`", () => {
  const rows = [
    // `official` would order these 1, 2, 3, 4; the visible glance names order them 4, 2, 3, 1.
    { id: "1", official: "Aakash Singh, Associate Deputy AG", glance: glance("DOJ under Pam Bondi") },
    { id: "2", official: "Adm. Kevin Lunday, Coast Guard", glance: glance("kevin Lunday (Coast Guard)") },
    { id: "3", official: "Andrew Boutros, U.S. Attorney", glance: glance("Lee Zeldin (EPA)") },
    { id: "4", official: "Ben Black, DFC CEO", glance: glance("Ben Black (DFC)") },
  ];
  assert.deepEqual(rows.sort(compareByCardTitle(cfg)).map(r => r.id), ["4", "1", "2", "3"]);
});

test("compareByCardTitle falls back to `official` when an entry has no valid glance, or the tracker's glance flag is off", () => {
  const rows = [
    { id: "a", official: "Todd Blanche, Deputy AG" },
    { id: "b", official: "kash Patel, FBI Director", glance: { who: "" } },
    { id: "c", official: "Kristi Noem, DHS Secretary", glance: glance("Zed Last") },
  ];
  // Glance on: b (invalid glance) and a (none) lead with `official`; c leads with its glance name "Zed Last".
  assert.deepEqual(rows.sort(compareByCardTitle(cfg)).map(r => r.id), ["b", "a", "c"]);
  assert.deepEqual(rows.sort(compareByCardTitle({ ...cfg, glanceEnabled: false })).map(r => r.id), ["b", "c", "a"], "flag off: all by official");
});

test("compareByCardTitle breaks ties by what the card says next, then by id, in a fixed order", () => {
  const rows = [
    { id: "b", official: "x", glance: glance("Bill Pulte (FHFA)", "Used mortgage data to refer critics") },
    { id: "z", official: "x", glance: glance("Bill Pulte (FHFA)", "Made a fundraiser a consultant") },
    { id: "a", official: "x", glance: glance("Bill Pulte (FHFA)", "Used mortgage data to refer critics") },
    { id: "m", official: "" },
  ];
  const expected = ["m", "z", "a", "b"];
  assert.deepEqual(rows.sort(compareByCardTitle(cfg)).map(r => r.id), expected);
  assert.deepEqual(rows.reverse().sort(compareByCardTitle(cfg)).map(r => r.id), expected, "same result from any starting order");
});

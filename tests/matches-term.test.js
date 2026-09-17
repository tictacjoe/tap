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
// matchesTerm calls escapeRegExp, which lives inside the highlight-matches
// marker block alongside highlightMatches itself -- pull both functions in
// so highlightMatches can be exercised the same way the running page uses
// it (matchesTerm deciding whether an entry matches, highlightMatches
// deciding what to <mark>).
const highlightMatchesFunctionSource = extractFunction(source, "highlight-matches");
const escapeHtmlFunctionSource = extractFunction(source, "escape-html");
const matchesTermFunctionSource = extractFunction(source, "matches-term");
const combined = escapeHtmlFunctionSource + "\n" + highlightMatchesFunctionSource + "\n" + matchesTermFunctionSource;
const { matchesTerm, highlightMatches } = (0, eval)(
  `${combined}\n({ matchesTerm, highlightMatches });`
);

test("plain mode: single word matches whole-word, case-insensitively", () => {
  assert.equal(matchesTerm("The EPA announced new rules.", "epa", false), true);
});

test("plain mode: single word does not match inside an unrelated word", () => {
  assert.equal(matchesTerm("The department issued a statement.", "epa", false), false);
});

test("plain mode: multi-word term matches when the words appear out of literal order", () => {
  // Regression: an earlier version wrapped the whole term in one \b...\b
  // pattern, so "aircraft carrier lincoln" only matched that exact three
  // -word phrase verbatim and missed real entries like the one below.
  assert.equal(
    matchesTerm(
      "The aircraft carrier USS Abraham Lincoln deployed to the region.",
      "aircraft carrier lincoln",
      false
    ),
    true
  );
});

test("plain mode: multi-word term requires every word to be present", () => {
  assert.equal(
    matchesTerm("The aircraft carrier USS Nimitz deployed.", "aircraft carrier lincoln", false),
    false
  );
});

test("regex mode: term is still matched as a literal phrase pattern", () => {
  assert.equal(
    matchesTerm("The aircraft carrier USS Nimitz deployed.", "aircraft carrier lincoln", true),
    false
  );
  assert.equal(
    matchesTerm("aircraft carrier lincoln class", "aircraft carrier lincoln", true),
    true
  );
});

test("regex mode: invalid pattern returns null", () => {
  assert.equal(matchesTerm("anything", "(unclosed", true), null);
});

test("highlightMatches: multi-word plain term highlights each word independently", () => {
  assert.equal(
    highlightMatches("Civil rights groups praised the ruling.", "civil rights", false),
    '<mark class="hl">Civil</mark> <mark class="hl">rights</mark> groups praised the ruling.'
  );
});

test("highlightMatches: multi-word plain term highlights words wherever they appear, not just adjacent", () => {
  assert.equal(
    highlightMatches("The aircraft carrier USS Abraham Lincoln deployed.", "aircraft carrier lincoln", false),
    'The <mark class="hl">aircraft</mark> <mark class="hl">carrier</mark> USS Abraham <mark class="hl">Lincoln</mark> deployed.'
  );
});

test('plain mode: quoted phrase requires the words adjacent, in order', () => {
  assert.equal(matchesTerm("The Supreme Court ruled today.", '"Supreme Court"', false), true);
  assert.equal(
    matchesTerm("A district court and the supreme leader both weighed in.", '"Supreme Court"', false),
    false
  );
});

test('plain mode: quoted phrase can combine with an independent unquoted word', () => {
  assert.equal(matchesTerm("EPA cited the Supreme Court ruling.", '"Supreme Court" EPA', false), true);
  assert.equal(matchesTerm("The Supreme Court ruled today.", '"Supreme Court" EPA', false), false);
});

test('plain mode: unterminated quote degrades to independent-word matching instead of matching nothing', () => {
  assert.equal(matchesTerm("The Supreme Court ruled today.", '"Supreme Court', false), true);
});

test('highlightMatches: quoted phrase highlights only the adjacent match, not stray occurrences of either word', () => {
  assert.equal(
    highlightMatches("The Supreme Court and a district court both ruled.", '"Supreme Court"', false),
    'The <mark class="hl">Supreme Court</mark> and a district court both ruled.'
  );
});

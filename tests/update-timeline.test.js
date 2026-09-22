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
const regionSource = extractFunction(source, "update-timeline");
const { sortUpdatesNewestFirst, updatesLabel, buildFieldTimelineHtml } = (0, eval)(
  `${regionSource}\n({ sortUpdatesNewestFirst, updatesLabel, buildFieldTimelineHtml });`);

const identity = (text) => text || "";
const upd = (text, date, label = "Update", effective = date) =>
  ({ date: date || null, label, text, effective_date: effective || null });

test("sortUpdatesNewestFirst orders by effective_date descending", () => {
  const a = upd("a", "2026-08-01"), b = upd("b", "2026-09-01"), c = upd("c", "2026-08-15");
  assert.deepEqual(sortUpdatesNewestFirst([a, b, c]).map(u => u.text), ["b", "c", "a"]);
});

test("sortUpdatesNewestFirst puts out-of-order written dates in true date order", () => {
  const first = upd("first", "2026-09-12"), second = upd("second", "2026-08-17"), third = upd("third", "2026-08-29");
  assert.deepEqual(sortUpdatesNewestFirst([first, second, third]).map(u => u.text), ["first", "third", "second"]);
});

test("sortUpdatesNewestFirst lets the later position win an equal-date tie", () => {
  const a = upd("a", "2026-08-01"), b = upd("b", "2026-08-01");
  assert.deepEqual(sortUpdatesNewestFirst([a, b]).map(u => u.text), ["b", "a"]);
});

test("sortUpdatesNewestFirst keeps an undated update next to the one it inherited from", () => {
  const dated = upd("dated", "2026-08-01"), bare = upd("bare", null, "Update", "2026-08-01");
  const newer = upd("newer", "2026-09-01");
  assert.deepEqual(sortUpdatesNewestFirst([dated, bare, newer]).map(u => u.text), ["newer", "bare", "dated"]);
});

test("sortUpdatesNewestFirst sorts a leading undated update (null effective_date) last", () => {
  const leading = upd("leading", null, "Update", null), dated = upd("dated", "2026-08-01");
  assert.deepEqual(sortUpdatesNewestFirst([leading, dated]).map(u => u.text), ["dated", "leading"]);
});

test("sortUpdatesNewestFirst does not mutate its input", () => {
  const input = [upd("a", "2026-08-01"), upd("b", "2026-09-01")];
  sortUpdatesNewestFirst(input);
  assert.deepEqual(input.map(u => u.text), ["a", "b"]);
});

test("updatesLabel wording for one update and for several", () => {
  assert.equal(updatesLabel(1), "Update, dated when TAP added it");
  assert.equal(updatesLabel(2), "Updates, newest first, dated when TAP added them");
});

test("buildFieldTimelineHtml renders base, label, then updates newest first", () => {
  const entry = {
    what_changed: "raw prose",
    timeline: { what_changed: { base: "Base.", updates: [
      upd("Update 2026-08-01: old.", "2026-08-01"), upd("Update 2026-09-01: new.", "2026-09-01")] } },
  };
  const html = buildFieldTimelineHtml(entry, "what_changed", identity);
  assert.equal(html,
    "<p>Base.</p>" +
    '<p class="update-timeline-label">Updates, newest first, dated when TAP added them</p>' +
    "<p>Update 2026-09-01: new.</p><p>Update 2026-08-01: old.</p>");
});

test("buildFieldTimelineHtml uses the single-update label for one update", () => {
  const entry = { status: "raw", timeline: { status: { base: "Base.", updates: [upd("Update 2026-08-01: x.", "2026-08-01")] } } };
  assert(buildFieldTimelineHtml(entry, "status", identity).includes(">Update, dated when TAP added it</p>"));
});

test("buildFieldTimelineHtml omits the base paragraph when the field starts with a marker", () => {
  const entry = { status: "raw", timeline: { status: { base: "", updates: [upd("Update 2026-08-01: x.", "2026-08-01")] } } };
  assert(buildFieldTimelineHtml(entry, "status", identity).startsWith('<p class="update-timeline-label">'));
});

test("buildFieldTimelineHtml passes every paragraph through hl", () => {
  const entry = { status: "raw", timeline: { status: { base: "Base.", updates: [upd("Update 2026-08-01: x.", "2026-08-01")] } } };
  const html = buildFieldTimelineHtml(entry, "status", (t) => t.toUpperCase());
  assert(html.includes("<p>BASE.</p>") && html.includes("<p>UPDATE 2026-08-01: X.</p>"));
});

test("buildFieldTimelineHtml falls back to one unsplit paragraph without a timeline entry", () => {
  assert.equal(buildFieldTimelineHtml({ status: "Plain. Update 2026-08-01: raw." }, "status", identity),
    "<p>Plain. Update 2026-08-01: raw.</p>");
  assert.equal(buildFieldTimelineHtml({ status: "P", timeline: {} }, "status", identity), "<p>P</p>");
});

test("buildFieldTimelineHtml renders nothing for an empty or missing field", () => {
  assert.equal(buildFieldTimelineHtml({}, "status", identity), "");
  assert.equal(buildFieldTimelineHtml({ status: "" }, "status", identity), "");
});

test("buildFieldTimelineHtml splits a marker-free field on blank lines into separate paragraphs (narrative_combined's merged prose)", () => {
  const entry = { incident_summary: "First paragraph.\n\nSecond paragraph.\n\nThird paragraph." };
  const html = buildFieldTimelineHtml(entry, "incident_summary", identity);
  assert.equal(html, "<p>First paragraph.</p><p>Second paragraph.</p><p>Third paragraph.</p>");
});

test("buildFieldTimelineHtml tolerates extra whitespace around a blank-line paragraph break", () => {
  const entry = { incident_summary: "First.\n\n  \nSecond." };
  const html = buildFieldTimelineHtml(entry, "incident_summary", identity);
  assert.equal(html, "<p>First.</p><p>Second.</p>");
});

test("buildFieldTimelineHtml passes each split paragraph through hl individually", () => {
  const entry = { incident_summary: "one\n\ntwo" };
  const html = buildFieldTimelineHtml(entry, "incident_summary", (t) => t.toUpperCase());
  assert.equal(html, "<p>ONE</p><p>TWO</p>");
});

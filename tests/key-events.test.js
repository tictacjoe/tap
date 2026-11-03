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

const source = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");

// Pull in the marker blocks the key-events renderer depends on, then
// expose the functions under test.
const harness = new Function(
  extractFunction(source, "escape-html") +
  extractFunction(source, "format-key-event-date") +
  extractFunction(source, "key-events-rail") +
  "return { escapeHtml, formatKeyEventDate, buildKeyEventsRailHtml };"
)();
const { formatKeyEventDate, buildKeyEventsRailHtml, escapeHtml } = harness;
const hl = (t) => escapeHtml(t);

test("formatKeyEventDate: first event shows full date with year", () => {
  assert.equal(formatKeyEventDate("2026-07-03", null), "Jul 3, 2026");
});

test("formatKeyEventDate: same year as previous drops the year", () => {
  assert.equal(formatKeyEventDate("2026-10-22", "2026-08-18"), "Oct 22");
});

test("formatKeyEventDate: year change shows the year", () => {
  assert.equal(formatKeyEventDate("2027-01-05", "2026-12-30"), "Jan 5, 2027");
});

test("formatKeyEventDate: month precision is Mon YYYY", () => {
  assert.equal(formatKeyEventDate("2026-10", "2026-09-01"), "Oct 2026");
});

test("formatKeyEventDate: year precision is YYYY", () => {
  assert.equal(formatKeyEventDate("2026", null), "2026");
});

const ev = (date, text, extra) => Object.assign({ date, text, sources: ["https://a.example/1"] }, extra || {});

test("rail: empty when no key_events", () => {
  assert.equal(buildKeyEventsRailHtml({}, hl), "");
  assert.equal(buildKeyEventsRailHtml({ key_events: [] }, hl), "");
});

test("rail: one li per event in array order", () => {
  const html = buildKeyEventsRailHtml({ key_events: [ev("2026-01-02", "First"), ev("2026-02-03", "Second")] }, hl);
  assert.ok(html.startsWith('<ol class="key-events" aria-label="Key events">'));
  assert.ok(html.endsWith("</ol>"));
  assert.equal((html.match(/<li /g) || []).length, 2);
  assert.ok(html.indexOf("First") < html.indexOf("Second"));
});

test("rail: turning point gets key-event-turning", () => {
  const html = buildKeyEventsRailHtml({ key_events: [ev("2026-01-02", "A"), ev("2026-02-03", "B", { turning_point: true })] }, hl);
  assert.equal((html.match(/key-event-turning/g) || []).length, 1);
  assert.ok(html.includes('<li class="key-event key-event-turning">'));
  assert.ok(html.includes('<li class="key-event">'));
});

test("rail: data-sources round-trips", () => {
  const sources = ["https://a.example/1?x=1&y=2", "https://b.example/\"q\""];
  const html = buildKeyEventsRailHtml({ key_events: [ev("2026-01-02", "A", { sources })] }, hl);
  const m = html.match(/data-sources="([^"]*)"/);
  assert.ok(m);
  const raw = m[1].replace(/&quot;/g, '"').replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
  assert.deepEqual(JSON.parse(raw), sources);
});

test("rail: escapes text and source urls", () => {
  const html = buildKeyEventsRailHtml({ key_events: [ev("2026-01-02", 'A < B & "C"', { sources: ['https://x.example/"onmouseover="y'] })] }, hl);
  const textSpan = html.match(/<span class="key-event-text">(.*?)<\/span>/)[1];
  assert.ok(!textSpan.includes("<"));
  assert.equal(textSpan, "A &lt; B &amp; &quot;C&quot;");
  assert.ok(!html.includes('"onmouseover="'));
  assert.equal((html.match(/data-sources="/g) || []).length, 1);
});

test("rail: dates use formatKeyEventDate with the previous event", () => {
  const html = buildKeyEventsRailHtml({ key_events: [ev("2026-08-18", "A"), ev("2026-10-22", "B"), ev("2027-01-05", "C")] }, hl);
  const dates = [...html.matchAll(/<span class="key-event-date">(.*?)<\/span>/g)].map((m) => m[1]);
  assert.deepEqual(dates, ["Aug 18, 2026", "Oct 22", "Jan 5, 2027"]);
});

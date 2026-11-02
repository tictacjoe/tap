// Status pills (UX refresh spec 5.6): the six stage names, the pill markup,
// and the per-tracker gate that keeps pills and status filters hidden until
// every entry of a tracker carries a valid `status_stage`.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function extractRegion(source, name) {
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
const region = extractRegion(source, "status-stage");
// The group-by sort lives in its own marker region; it needs STATUS_STAGES.
const groupRegion = extractRegion(source, "status-stage-group");
const { STATUS_STAGES, statusPillHtml, trackerHasStatusStage, stageOrCategory,
        statusStageGroupKey, sortGroupsByStatusStage } = (0, eval)(
  `${region}\n${groupRegion}\n({ STATUS_STAGES, statusPillHtml, trackerHasStatusStage, stageOrCategory, statusStageGroupKey, sortGroupsByStatusStage });`
);

// Text a reader sees: tags (and their attributes) removed.
const visibleText = (html) => html.replace(/<[^>]*>/g, "");

test("the six stages, exact strings, in spec order", () => {
  assert.deepEqual(STATUS_STAGES.map(s => s.name), [
    "Reversed or withdrawn",
    "Court ruled",
    "In court",
    "Finding issued",
    "Under investigation",
    "Unchallenged",
  ]);
  assert.deepEqual(STATUS_STAGES.map(s => s.symbol), ["↺", "⚖", "⧗", "✎", "◔", "○"]);
  assert.deepEqual(STATUS_STAGES.map(s => s.cls), ["s-rev", "s-ruled", "s-court", "s-find", "s-inv", "s-none"]);
});

test("no pill without the field", () => {
  assert.equal(statusPillHtml(undefined, false), "");
  assert.equal(statusPillHtml(null, true), "");
  assert.equal(statusPillHtml("", false), "");
});

test("never a pill for Other/Unclassified or any unknown stage", () => {
  assert.equal(statusPillHtml("Other/Unclassified", false), "");
  assert.equal(statusPillHtml("Other/Unclassified", true), "");
  assert.equal(statusPillHtml("Court Ruled Against the Agency", false), "");
  assert.equal(statusPillHtml("in court", false), "");
});

test("full pill: symbol plus words", () => {
  const html = statusPillHtml("In court", false);
  assert.ok(html.includes("⧗"));
  assert.ok(html.includes("In court"));
  assert.equal(html, '<span class="status-pill s-court">⧗ In court</span>');
});

test("compact pill: symbol only, name as aria-label and title", () => {
  const html = statusPillHtml("In court", true);
  assert.ok(html.includes('aria-label="In court"'));
  assert.ok(html.includes('title="In court"'));
  assert.ok(html.includes("⧗"));
  assert.ok(!visibleText(html).includes("In court"));
  assert.equal(visibleText(html), "⧗");
});

test("every stage renders its own class and symbol", () => {
  STATUS_STAGES.forEach(s => {
    const html = statusPillHtml(s.name, false);
    assert.ok(html.includes('class="status-pill ' + s.cls + '"'), html);
    assert.equal(visibleText(html), s.symbol + " " + s.name);
  });
});

test("trackerHasStatusStage: true only when every entry has a valid stage", () => {
  const trackers = {
    all: { data: [{ status_stage: "In court" }, { status_stage: "Unchallenged" }] },
    some: { data: [{ status_stage: "In court" }, {}] },
    bad: { data: [{ status_stage: "In court" }, { status_stage: "Other/Unclassified" }] },
    none: { data: [{}, {}] },
    empty: { data: [] },
    hidden: { hidden: true, data: [{ status_stage: "In court" }] },
  };
  assert.equal(trackerHasStatusStage("all", trackers), true);
  assert.equal(trackerHasStatusStage("some", trackers), false);
  assert.equal(trackerHasStatusStage("bad", trackers), false);
  assert.equal(trackerHasStatusStage("none", trackers), false);
  assert.equal(trackerHasStatusStage("empty", trackers), false);
  assert.equal(trackerHasStatusStage("hidden", trackers), false);
  assert.equal(trackerHasStatusStage("missing", trackers), false);
});

test("stageOrCategory: stage when live, category otherwise", () => {
  const e = { status_stage: "In court", status_category: "Alleged" };
  assert.equal(stageOrCategory(e, { statusStageLive: true }), "In court");
  assert.equal(stageOrCategory(e, { statusStageLive: false }), "Alleged");
  assert.equal(stageOrCategory(e, {}), "Alleged");
});

test("group-by uses STATUS_STAGES order across all six stages", () => {
  // Entries deliberately in reverse order; group exactly as the shipped
  // renderer does (key function, then the shipped group sort).
  const entries = STATUS_STAGES.map(s => ({ status_stage: s.name })).reverse();
  const groups = new Map();
  entries.forEach(e => {
    const k = statusStageGroupKey(e);
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(e);
  });
  const sorted = sortGroupsByStatusStage([...groups.entries()]);
  assert.deepEqual(sorted.map(g => g[0]), STATUS_STAGES.map(s => s.name));
});

test("compact pills at 600px", () => {
  const m = source.match(/function useCompactPills\(\) \{[\s\S]*?\n\}/);
  assert.ok(m, "useCompactPills not found");
  assert.ok(m[0].includes("(max-width: 600px)"));
  assert.ok(!m[0].includes("480px"));
});

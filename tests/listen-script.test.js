// Tests for the Listen button's spoken-text builder (the listen-script
// region of index.html). Spec:
// tap-data/docs/superpowers/specs/2026-10-31-tap-entry-listen-button-design.md
// The builder turns one curated entry into the ordered list of sections the
// player speaks: quick listen, the "Here's the full entry." cue, the full
// sections in the tracker's own order, and the confidence-summary close.
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

const siteDir = path.join(__dirname, "..");
const source = fs.readFileSync(path.join(siteDir, "index.html"), "utf8");
// The builder reuses the page's own cleanup and timeline helpers so what is
// spoken always matches what is shown -- pull every region it depends on.
const combined = ["strip-process-labels", "update-timeline", "violation-concern-value", "glance-head", "listen-script"]
  .map(n => extractFunction(source, n)).join("\n");
const { spokenDate, speakableText, splitForSpeech, buildListenScript } =
  (0, eval)(`${combined}\n({ spokenDate, speakableText, splitForSpeech, buildListenScript });`);

const claCfg = { kind: "prosecution", label: "Cabinet-Level Accountability", titleField: "official", glanceEnabled: true };
const deregCfg = { kind: "deregulation", label: "Corporate Deregulation", titleField: "rule_name", glanceEnabled: true };
const daiCfg = {
  kind: "govservices", trackerKey: "dai", label: "DHS and ICE", titleField: "title", glanceEnabled: true,
  fieldLabels: { institution: "Agencies", proponent: "Lead official", impact: "Human toll" },
};

function claEntry(overrides) {
  return Object.assign({
    official: "Pam Bondi",
    glance: { who: "Pam Bondi", what: "fired prosecutors", harm: { kind: "institutional", who: "career staff", certainty: "documented" } },
    offense_category: "Abuse of power",
    status_category: "Alleged",
    date_of_action: "2026-02",
    section_summaries: { incident_summary: "S1", status: "S2", confidence_note: "C1" },
    incident_summary: "Full story.",
    status: "Still pending.",
    cause: "Pattern.",
    offense_category_raw: "18 U.S.C.",
    rebuttal_anticipated: "Defense.",
    comeback: "Rebuttal.",
  }, overrides);
}

test("spokenDate converts full and month dates", () => {
  assert.equal(spokenDate("2026-03-04"), "March 4, 2026");
  assert.equal(spokenDate("2025-03"), "March 2025");
  assert.equal(spokenDate("2025-13"), "2025-13");
});

test("drops re-verified lead", () => {
  assert.equal(speakableText("Stay ordered. Re-verified 2026-07-26: no material change -- the court ruled."),
    "Stay ordered. No material change, the court ruled.");
});

test("converts compound date_of_action", () => {
  assert.equal(speakableText("2025-03 (wrongful deportation to CECOT) through 2026-05 (case dismissed)"),
    "March 2025 (wrongful deportation to CECOT) through May 2026 (case dismissed)");
});

test("TAP becomes Tap, bold and brackets removed", () => {
  assert.equal(speakableText("**[TAP Analysis, not sourced]** TAP's view"), "Tap analysis, not sourced. Tap's view");
  assert.equal(speakableText("STAPLES"), "STAPLES");
});

// Review fix 2026-10-31: the bracketed honesty marker ran straight into the
// next sentence once its brackets were stripped; it now ends with a full stop.
test("TAP Analysis marker is spoken as its own sentence", () => {
  assert.equal(speakableText("[TAP Analysis, not sourced] Consistent with a pattern."),
    "Tap analysis, not sourced. Consistent with a pattern.");
});

// Review fix: 220 characters is ~15 s at rate 1, right at Chrome's cut-off
// for network voices; the default chunk is now 160.
test("splitForSpeech defaults to 160-character chunks", () => {
  const text = Array.from({ length: 30 }, (_, i) => "Short sentence " + i + ".").join(" ");
  assert.ok(splitForSpeech(text).every(c => c.length <= 160));
  assert.ok(splitForSpeech(text).some(c => c.length > 140));
});

test("splitForSpeech keeps chunks under maxLen and loses no words", () => {
  const sentence = "The agency said the rule, which covers mines and quarries, would stay in effect for now";
  const para = Array.from({ length: 7 }, (_, i) => sentence + " " + i + ".").join(" ");
  const longOne = Array.from({ length: 40 }, () => "word").join(" ") + ", " + Array.from({ length: 40 }, () => "more").join(" ") + ".";
  const text = para + "\n\n" + longOne;
  const chunks = splitForSpeech(text);
  assert.ok(chunks.length > 2);
  assert.ok(chunks.every(c => c.length <= 220 && c === c.trim() && c !== ""));
  assert.deepEqual(chunks.join(" ").split(/\s+/), text.split(/\s+/));
});

test("quick listen then cue then full, CLA glance entry", () => {
  const script = buildListenScript(claEntry(), claCfg);
  assert.deepEqual(script.map(s => s.label), ["At a glance", "What happened", "Status", "Full entry", "What happened", "Status",
    "Broader Pattern", "Violation Type, in full", "Anticipated Defense", "Tap's Rebuttal", "How solid is this?"]);
  assert.equal(script[0].text, "Cabinet-Level Accountability. Date of action: February 2026. Pam Bondi: fired prosecutors. Harm to: career staff. Harm status: documented. Violation or concern type: Abuse of power. Status stage: Alleged.");
  assert.equal(script[1].text, "What happened. S1");
  assert.equal(script[3].text, "Here's the full entry.");
  assert.equal(script[4].text, "What happened. Full story.");
  assert.ok(!script.slice(4).some(s => s.text.includes("S1") || s.text.includes("S2")));
  assert.ok(!script.some(s => s.text.includes("C1") && s.label !== "How solid is this?"));
  assert.equal(script[script.length - 1].text, "How solid is this? C1");
});

test("concern-type caveat is spoken", () => {
  const script = buildListenScript(claEntry({ offense_category: "Other/Unclassified", concern_type: "Ethics concern" }), claCfg);
  assert.match(script[0].text, /Violation or concern type: Ethics concern, not alleged as a legal violation\. Status stage: Alleged\.$/);
});

test("no glance falls back to title and reads the aside cards", () => {
  const script = buildListenScript(claEntry({ glance: undefined }), claCfg);
  assert.equal(script[0].text, "Cabinet-Level Accountability. Date of action: February 2026. Pam Bondi.");
  const labels = script.map(s => s.label);
  const full = labels.indexOf("Full entry");
  assert.deepEqual(labels.slice(full + 1, full + 5), ["What happened", "Violation or concern type", "Status stage", "Status"]);
});

test("narrative_combined CLA reads status inside What happened", () => {
  const script = buildListenScript(claEntry({ narrative_combined: true }), claCfg);
  const labels = script.map(s => s.label);
  const full = labels.indexOf("Full entry");
  assert.equal(script[full + 1].text, "What happened. Full story.\n\nStill pending.");
  assert.ok(!labels.slice(full + 1).includes("Status"));
});

test("timeline: base, label, updates newest first, no update dates", () => {
  const entry = claEntry({
    timeline: { status: { base: "Base.", updates: [
      { date: "2026-01-01", effective_date: "2026-01-01", label: "Update", text: "Update 2026-01-01: older." },
      { date: "2026-05-01", effective_date: "2026-05-01", label: "Update", text: "Update 2026-05-01: newer." },
    ] } },
  });
  const script = buildListenScript(entry, claCfg);
  const full = script.findIndex(s => s.label === "Full entry");
  const status = script.slice(full).find(s => s.label === "Status");
  assert.equal(status.text, "Status. Base.\n\nUpdates, newest first.\n\nNewer.\n\nOlder.");
});

test("deregulation order, impact caveat and proponent", () => {
  const entry = {
    rule_name: "Mine dust rule",
    glance: { who: "MSHA", what: "paused a silica rule", harm: { kind: "physical", who: "miners", certainty: "projected" } },
    section_summaries: { what_changed: "W1", estimated_impact: "E1", confidence_note: "C1" },
    what_changed: "Paused.", status: "Stayed.",
    estimated_health_impact: { summary: "More illness.", caveat: "Estimates vary." },
    primary_proponent: { name: "Jane Roe", role: "MSHA head", note: "Signed the order." },
  };
  const script = buildListenScript(entry, deregCfg);
  assert.deepEqual(script.map(s => s.label), ["At a glance", "What happened", "Estimated impact", "Full entry",
    "What happened", "Status", "Estimated impact", "Primary proponent", "How solid is this?"]);
  assert.equal(script[6].text, "Estimated impact. More illness. Caveat. Estimates vary.");
  assert.equal(script[7].text, "Primary proponent. Jane Roe, MSHA head. Signed the order.");
});

test("DAI uses human_toll summary, people and legal status", () => {
  const entry = {
    title: "Raid", glance: { who: "ICE", what: "raided a farm", harm: { kind: "rights", who: "workers", certainty: "documented" } },
    section_summaries: { what_changed: "W1", human_toll: "H1", confidence_note: "C1" },
    what_changed: "Agents arrived.", status: "Ongoing.",
    estimated_impact: { summary: "Forty detained." },
    people: { officials: [{ name: "Tom Homan", role: "border czar" }], agents: [], affected: [{ name: "Ana Diaz", description: "farmworker" }] },
    legal_status: "No charges filed.",
    institution: "ICE", primary_proponent: { name: "Tom Homan", role: "border czar" },
  };
  const script = buildListenScript(entry, daiCfg);
  const labels = script.map(s => s.label);
  assert.equal(script[2].text, "Human toll. H1");
  assert.deepEqual(labels.slice(labels.indexOf("Full entry") + 1), ["What happened", "Status", "Human toll", "People",
    "Legal status, not a finding", "Agencies", "Lead official", "How solid is this?"]);
  assert.equal(script[labels.indexOf("People")].text, "People. Officials: Tom Homan, border czar. Affected: Ana Diaz, farmworker.");
});

test("empty sections omitted", () => {
  const script = buildListenScript(claEntry({ cause: "", comeback: undefined, section_summaries: {} }), claCfg);
  const labels = script.map(s => s.label);
  assert.ok(!labels.includes("Broader Pattern") && !labels.includes("Tap's Rebuttal") && !labels.includes("How solid is this?"));
  assert.ok(script.every(s => !/\bundefined\b|\bnull\b/.test(s.text)));
});

test("corpus: every published curated entry speaks cleanly", () => {
  // Mirrors TRACKERS in index.html (label, titleField, kind, fieldLabels) --
  // keep in sync if a tracker is added or relabelled.
  const trackers = {
    prosecution: claCfg,
    deregulation: deregCfg,
    "government-services": { kind: "govservices", label: "Government Service Redirection", titleField: "title", glanceEnabled: true },
    trumpfamily: { kind: "govservices", trackerKey: "trumpfamily", label: "Trump Family", titleField: "title", glanceEnabled: true,
      fieldLabels: { institution: "Business", proponent: "Government link", impact: "Financial stake" } },
    dai: daiCfg,
    oea: { kind: "govservices", trackerKey: "oea", label: "Other Executive Actions", titleField: "title", glanceEnabled: true },
  };
  // A leaked JS value shows up as a whole field ("Status. undefined."), not as a word inside prose
  // ("over undefined 'DEI'" is real text), so match it only standing alone between separators.
  const bad = /(^|[:.]\s)(undefined|null)\.?(\s|$)|\*\*|<\/?[a-z]|https?:\/\/|Re-verified \d{4}|\b\d{4}-(0[1-9]|1[0-2])\b| -- /;
  let checked = 0;
  for (const [file, cfg] of Object.entries(trackers)) {
    const entries = JSON.parse(fs.readFileSync(path.join(siteDir, "data", file + ".json"), "utf8"));
    for (const entry of entries) {
      const script = buildListenScript(entry, cfg);
      assert.ok(script.length >= 3, `${file}/${entry.id}: only ${script.length} sections`);
      for (const s of script) {
        assert.ok(s.text.trim() !== "", `${file}/${entry.id}: empty ${s.label}`);
        const m = s.text.match(bad);
        assert.ok(!m, `${file}/${entry.id} ${s.label}: unspeakable "${m && m[0]}" in ${m && s.text.slice(Math.max(0, m.index - 40), m.index + 40)}`);
      }
      checked++;
    }
  }
  assert.ok(checked > 900);
});

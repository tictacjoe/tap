#!/usr/bin/env node
// build_index.js <site-root> [--check]
//
// Builds data/index/<file>.json: a slim copy of every curated entry holding only
// the fields the site needs to list, sort, filter and group rows before the full
// entries have loaded. Run by publish.py after the data files are written.
//
// Safety net: for every entry the SITE'S OWN functions (impactScore, rowSortKey,
// the Records adapters, group keys ...) are run on both the full entry and its
// slim projection, and any difference is a problem. If a tracker has a problem,
// its index file is deleted (the site then falls back to the full file) and the
// exit code is 1. --check writes and deletes nothing.
//
// The site functions are borrowed from index.html, which is never modified: by
// /* name:start */ ... /* name:end */ marker regions (as tests/headline-adapters
// does) or by brace matching on the function name (as cla_concern_ids.js does).
const fs = require("node:fs");
const path = require("node:path");

// Site tracker key -> file name under data/ (and under data/index/).
const INDEX_FILES = {
  prosecution: "prosecution.json",
  deregulation: "deregulation.json",
  govservices: "government-services.json",
  trumpfamily: "trumpfamily.json",
  dai: "dai.json",
};

// ---------------------------------------------------------------- site code

const source = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");

function region(name) {
  const a = `/* ${name}:start */`, b = `/* ${name}:end */`;
  const s = source.indexOf(a), e = source.indexOf(b);
  if (s === -1 || e === -1) throw new Error(`markers for ${name} not found in index.html`);
  return source.slice(s + a.length, e);
}

// From `token` (e.g. "function impactScore" or "const ROW_SORTS =") to the
// closing brace of the first {...} after it.
function extractBlock(token) {
  const at = source.indexOf(token);
  if (at === -1) throw new Error(`${token} not found in index.html`);
  const m = source.slice(at);
  let depth = 0, end = -1;
  for (let j = m.indexOf("{"); j < m.length; j++) {
    if (m[j] === "{") depth++;
    if (m[j] === "}") { depth--; if (depth === 0) { end = j; break; } }
  }
  if (end === -1) throw new Error(`${token}: closing brace not found`);
  return m.slice(0, end + 1);
}

const regions = [
  "evidence-drawer", "truncate", "combine-tier-text", "fullest-tier-text", "pack-headline",
  "strip-process-labels", "strip-adapted-item-labels",
  "adapt-deregulation-entry", "adapt-govservices-entry", "adapt-trumpfamily-entry",
  "adapt-dai-entry", "adapt-prosecution-entry",
  "map-trumpfamily-entry", "map-dai-entry", "family-group-keys", "dai-group-keys",
  "status-stage", "classify-status", "glance-head",
].map(region);
const blocks = [
  extractBlock("function extractLargestNumber"),
  extractBlock("function impactScore"),
  extractBlock("function coverageCount"),
  extractBlock("function classifyOffenseCategory"),
  extractBlock("function classifyConcernType"),
  extractBlock("const ROW_SORTS ="),
  extractBlock("function rowSortKey"),
  "const TRACKERS = " + extractBlock("const TRACKERS =").replace(/^const TRACKERS =\s*/, ""),
];
const site = (0, eval)(`${regions.join("\n")}\n${blocks.join(";\n")};
({ impactScore, coverageCount, isValidGlance, rowSortKey, ROW_SORTS, TRACKERS, isRecheckNote,
   mapTrumpFamilyEntry, mapDaiEntry, familyGroupKeys, daiAgencyGroupKeys, daiOfficialGroupKeys,
   classifyOffenseCategory, classifyStatus, classifyConcernType,
   adaptDeregulationEntry, adaptGovServicesEntry, adaptTrumpFamilyEntry, adaptDaiEntry, adaptProsecutionEntry });`);

const ADAPTERS = {
  deregulation: site.adaptDeregulationEntry, govservices: site.adaptGovServicesEntry,
  trumpfamily: site.adaptTrumpFamilyEntry, dai: site.adaptDaiEntry, prosecution: site.adaptProsecutionEntry,
};

// ---------------------------------------------------------------- projection

// Copy `keys` of `src` onto `out`, leaving out any key the source lacks.
function copyKeys(out, src, keys) {
  for (const k of keys) if (src[k] !== undefined) out[k] = src[k];
}
const figuresOnly = (block) => (block && Array.isArray(block.figures))
  ? { figures: block.figures.map((f) => (f && f.value !== undefined ? { value: f.value } : {})) }
  : undefined;
const blanks = (list) => (Array.isArray(list) ? list.map(() => ({})) : undefined);
const headlineOf = (e) => e.narrative_override && e.narrative_override.headline;

const COMMON = ["id", "glance", "status_stage", "date_of_action", "date_added", "last_verified", "last_substantive_update"];
const TITLE = { prosecution: "official", deregulation: "rule_name", govservices: "title", trumpfamily: "title", dai: "title" };

function projectEntry(trackerKey, e) {
  if (!TITLE[trackerKey]) throw new Error(`unknown tracker ${trackerKey}`);
  const out = {};
  copyKeys(out, e, [COMMON[0], TITLE[trackerKey], ...COMMON.slice(1)]);
  const headline = headlineOf(e);
  if (headline) out.narrative_override = { headline };
  const ss = e.section_summaries || {};
  const summaryKey = trackerKey === "prosecution" ? "incident_summary" : "what_changed";
  if (ss[summaryKey] !== undefined) out.section_summaries = { [summaryKey]: ss[summaryKey] };

  const set = (k, v) => { if (v !== undefined) out[k] = v; };
  if (trackerKey === "deregulation") {
    copyKeys(out, e, ["domain", "short_summary"]);
    set("estimated_health_impact", figuresOnly(e.estimated_health_impact));
    set("sources", blanks(e.sources));
    if (!headline && !e.short_summary) copyKeys(out, e, ["what_changed"]);
  } else if (trackerKey === "govservices") {
    copyKeys(out, e, ["domain"]);
    set("estimated_impact", figuresOnly(e.estimated_impact));
    set("sources", blanks(e.sources));
  } else if (trackerKey === "trumpfamily") {
    copyKeys(out, e, ["category", "family_members"]);
    const n = e.government_nexus;
    if (n) {
      const g = {};
      if (n.official) g.official = n.official.name !== undefined ? { name: n.official.name } : {};
      if (Array.isArray(n.also_officials)) g.also_officials = n.also_officials.map((o) => (o && o.name !== undefined ? { name: o.name } : {}));
      out.government_nexus = g;
    }
    set("financial_stake", figuresOnly(e.financial_stake));
    set("sources", blanks(e.sources));
  } else if (trackerKey === "dai") {
    copyKeys(out, e, ["category", "agencies"]);
    if (e.people && Array.isArray(e.people.officials)) {
      out.people = { officials: e.people.officials.map((o) => {
        const r = {};
        if (o && o.name !== undefined) r.name = o.name;
        if (o && o.role !== undefined) r.role = o.role;
        return r;
      }) };
    }
    set("human_toll", figuresOnly(e.human_toll));
    set("sources", blanks(e.sources));
  } else { // prosecution (CLA)
    copyKeys(out, e, ["contested", "offense_category", "status"]);
    if (typeof e.confidence_note === "string") out.confidence_note = e.confidence_note.trim().split(/\s+/)[0];
    if (Array.isArray(e.evidence)) out.evidence = e.evidence.filter((ev) => !site.isRecheckNote(ev)).map(() => ({}));
    if (!headline && ss.incident_summary === undefined) copyKeys(out, e, ["incident_summary"]);
  }
  return out;
}

// ------------------------------------------------------------------- parity

// An entry the way the site holds it after loading: the mappers for TFS/DAI,
// the classification (on a copy) for CLA.
function prepare(trackerKey, e) {
  if (trackerKey === "trumpfamily") return site.mapTrumpFamilyEntry(e);
  if (trackerKey === "dai") return site.mapDaiEntry(e);
  if (trackerKey === "prosecution") {
    const c = Object.assign({}, e);
    c.offense_category_raw = e.offense_category;
    c.offense_category = site.classifyOffenseCategory(e.offense_category);
    c.status_category = site.classifyStatus(e.status);
    c.concern_type = c.offense_category === "Other/Unclassified" ? site.classifyConcernType(c.offense_category_raw) : null;
    return c;
  }
  return Object.assign({}, e);
}

const nexusNames = (e) => {
  const n = e.government_nexus || {};
  return [(n.official || {}).name].concat((n.also_officials || []).map((o) => o && o.name));
};

// Each check: [name, fn(preparedEntry, cfg) -> comparable value].
function checks(trackerKey) {
  const list = [
    ["impactScore", (e, c) => site.impactScore(e, c)],
    ["coverageCount", (e, c) => site.coverageCount(e, c)],
    ["isValidGlance", (e) => site.isValidGlance(e.glance)],
  ];
  for (const k of Object.keys(site.ROW_SORTS)) list.push([`rowSortKey ${k}`, (e, c) => site.rowSortKey(e, c, k)]);
  list.push(["filter", (e) => (trackerKey === "prosecution" ? e.status_stage : e.domain)]);
  if (trackerKey === "trumpfamily") {
    list.push(["familyGroupKeys", (e) => site.familyGroupKeys(e)]);
    list.push(["nexus names", nexusNames]);
  }
  if (trackerKey === "dai") {
    list.push(["daiAgencyGroupKeys", (e) => site.daiAgencyGroupKeys(e)]);
    list.push(["daiOfficialGroupKeys", (e) => site.daiOfficialGroupKeys(e)]);
  }
  if (trackerKey === "prosecution") {
    list.push(["official", (e) => e.official]);
    for (const k of ["offense_category", "status_category", "concern_type"]) list.push([k, (e) => e[k]]);
  }
  const adapt = ADAPTERS[trackerKey];
  const adapted = (pick) => (e) => pick(adapt(e));
  for (const k of ["headline", "date", "statusStage", "category", "id", "skim"]) list.push([`adapter ${k}`, adapted((a) => a[k])]);
  list.push(["adapter trail.lastSubstantiveUpdate", adapted((a) => a.trail.lastSubstantiveUpdate)]);
  list.push(["adapter trail.dateAdded", adapted((a) => a.trail.dateAdded)]);
  return list;
}

function parityProblems(trackerKey, full, slim) {
  const cfg = site.TRACKERS[trackerKey];
  const a = prepare(trackerKey, full), b = prepare(trackerKey, slim);
  const problems = [];
  for (const [name, fn] of checks(trackerKey)) {
    let va, vb;
    try { va = JSON.stringify(fn(a, cfg)); } catch (err) { va = "threw " + err.message; }
    try { vb = JSON.stringify(fn(b, cfg)); } catch (err) { vb = "threw " + err.message; }
    if (va !== vb) problems.push(`${full.id}: ${name} differs`);
  }
  return problems;
}

module.exports = { INDEX_FILES, projectEntry, parityProblems };

// ---------------------------------------------------------------------- CLI

function main(argv) {
  const root = argv.find((a) => !a.startsWith("--"));
  const checkOnly = argv.includes("--check");
  if (!root) {
    console.error("usage: node tools/build_index.js <site-root> [--check]");
    return 2;
  }
  const outDir = path.join(root, "data", "index");
  let failed = false;
  for (const [key, file] of Object.entries(INDEX_FILES)) {
    const src = path.join(root, "data", file), dest = path.join(outDir, file);
    // publish.py skips a tracker whose source folder is missing, so its data
    // file may not exist: no index for it, and no failure.
    if (!fs.existsSync(src)) {
      if (!checkOnly) fs.rmSync(dest, { force: true });
      continue;
    }
    const entries = JSON.parse(fs.readFileSync(src, "utf8"));
    const slim = entries.map((e) => projectEntry(key, e));
    const problems = entries.flatMap((e, i) => parityProblems(key, e, slim[i]));
    if (problems.length) {
      failed = true;
      problems.forEach((p) => console.error(`${key}: ${p}`));
      if (!checkOnly) fs.rmSync(dest, { force: true });
    } else if (!checkOnly) {
      fs.mkdirSync(outDir, { recursive: true });
      fs.writeFileSync(dest, JSON.stringify(slim, null, 2) + "\n");
      console.log(`${key}: wrote data/index/${file} (${slim.length} entries)`);
    }
  }
  return failed ? 1 : 0;
}

if (require.main === module) process.exitCode = main(process.argv.slice(2));

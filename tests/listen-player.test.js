// Tests for the Listen button's player controller (the listen-player region
// of index.html). The controller drives an injected speechSynthesis-like
// object, so these tests hand it a fake that records every utterance and
// lets the test fire onend/onerror by hand -- the same events a real
// browser engine fires.
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
// listen-player chunks text with splitForSpeech, which lives in listen-script
// (along with helpers it never calls here, so they need no dependencies).
const combined = ["listen-script", "listen-player"].map(n => extractFunction(source, n)).join("\n");
const { createListenPlayer, pickListenVoice } = (0, eval)(`${combined}\n({ createListenPlayer, pickListenVoice });`);

class FakeUtterance {
  constructor(text) { this.text = text; }
}

function fakeSynth() {
  return {
    spoken: [], cancels: 0, pauses: 0, resumes: 0,
    speaking: false, pending: false, paused: false,
    speak(u) { this.spoken.push(u); this.speaking = true; },
    cancel() { this.cancels++; this.speaking = false; },
    pause() { this.pauses++; this.paused = true; },
    resume() { this.resumes++; this.paused = false; },
    getVoices() { return [{ name: "Fred", lang: "en-US" }]; },
    last() { return this.spoken[this.spoken.length - 1]; },
  };
}

const twoSections = [{ label: "One", text: "One. First." }, { label: "Two", text: "Two. Second." }];

function setup() {
  const synth = fakeSynth();
  const states = [];
  const player = createListenPlayer(synth, FakeUtterance, s => states.push(s));
  return { synth, states, player };
}

test("speaks sections in order and goes idle at the end", () => {
  const { synth, player, states } = setup();
  player.start("cla/a", "Entry A", twoSections);
  assert.equal(player.state().status, "playing");
  assert.equal(player.state().label, "One");
  synth.last().onend();
  assert.equal(synth.last().text, "Two. Second.");
  synth.last().onend();
  assert.deepEqual(synth.spoken.map(u => u.text), ["One. First.", "Two. Second."]);
  assert.equal(player.state().status, "idle");
  assert.equal(states[states.length - 1].status, "idle");
});

test("utterances use rate 1 and the picked voice", () => {
  const { synth, player } = setup();
  player.start("cla/a", "Entry A", twoSections);
  assert.equal(synth.last().rate, 1);
  assert.equal(synth.last().voice.name, "Fred");
  assert.equal(synth.last().lang, "en-US");
});

test("next skips to the following section", () => {
  const { synth, player } = setup();
  player.start("cla/a", "Entry A", twoSections);
  player.next();
  assert.equal(synth.last().text, "Two. Second.");
  assert.equal(player.state().label, "Two");
  assert.equal(player.state().sectionIndex, 1);
  player.next();
  assert.equal(player.state().status, "idle");
});

test("ignores stale end events", () => {
  const { synth, player } = setup();
  player.start("cla/a", "Entry A", twoSections);
  const old = synth.last();
  player.next();
  const count = synth.spoken.length;
  old.onend();
  assert.equal(synth.spoken.length, count);
  assert.equal(player.state().sectionIndex, 1);
  assert.equal(player.state().status, "playing");
});

test("start on a new entry replaces the old one", () => {
  const { synth, player } = setup();
  player.start("cla/a", "Entry A", twoSections);
  const oldUtterance = synth.last();
  const cancels = synth.cancels;
  player.start("cla/b", "Entry B", [{ label: "B", text: "B text." }]);
  assert.ok(synth.cancels > cancels);
  assert.equal(player.state().key, "cla/b");
  assert.equal(player.state().title, "Entry B");
  const count = synth.spoken.length;
  oldUtterance.onend();
  assert.equal(synth.spoken.length, count);
});

test("toggle pauses and resumes", () => {
  const { synth, player } = setup();
  player.start("cla/a", "Entry A", twoSections);
  player.toggle();
  assert.equal(synth.pauses, 1);
  assert.equal(player.state().status, "paused");
  player.toggle();
  assert.equal(synth.resumes, 1);
  assert.equal(player.state().status, "playing");
});

test("resume after interruption respeaks current chunk", () => {
  const { synth, player } = setup();
  player.start("cla/a", "Entry A", twoSections);
  synth.last().onend();                     // now on section Two
  synth.speaking = false; synth.pending = false;   // browser dropped speech while hidden
  player.markInterrupted();
  assert.equal(player.state().status, "paused");
  const count = synth.spoken.length;
  player.toggle();
  assert.equal(synth.spoken.length, count + 1);
  assert.equal(synth.last().text, "Two. Second.");
  assert.equal(player.state().status, "playing");
});

test("markInterrupted leaves a live reading alone", () => {
  const { player } = setup();
  player.start("cla/a", "Entry A", twoSections);   // fake is still speaking
  player.markInterrupted();
  assert.equal(player.state().status, "playing");
});

test("interrupted/canceled errors do not advance", () => {
  const { synth, player } = setup();
  player.start("cla/a", "Entry A", twoSections);
  const count = synth.spoken.length;
  synth.last().onerror({ error: "interrupted" });
  synth.last().onerror({ error: "canceled" });
  assert.equal(synth.spoken.length, count);
  synth.last().onerror({ error: "synthesis-failed" });
  assert.equal(synth.last().text, "Two. Second.");
});

// Found in a real Chrome 2026-10-31: speech not started by a real tap fails
// every utterance with "not-allowed", and advancing on it flashed through the
// whole entry in silence and closed the bar. It must pause in place instead,
// so the listener's Resume tap (a real gesture) retries the same chunk.
test("not-allowed pauses in place instead of skipping", () => {
  const { synth, player } = setup();
  player.start("cla/a", "Entry A", twoSections);
  const count = synth.spoken.length;
  synth.speaking = false;
  synth.last().onerror({ error: "not-allowed" });
  assert.equal(synth.spoken.length, count);
  assert.equal(player.state().status, "paused");
  assert.equal(player.state().sectionIndex, 0);
  player.toggle();
  assert.equal(synth.last().text, "One. First.");
  assert.equal(player.state().status, "playing");
});

test("long sections are spoken in chunks", () => {
  const { synth, player } = setup();
  const long = Array.from({ length: 12 }, (_, i) => "Sentence number " + i + " is here to make this long.").join(" ");
  player.start("cla/a", "Entry A", [{ label: "Long", text: long }]);
  let guard = 0;
  while (player.state().status === "playing" && guard++ < 50) synth.last().onend();
  assert.ok(synth.spoken.length > 1);
  assert.ok(synth.spoken.every(u => u.text.length <= 220));
  assert.equal(synth.spoken.map(u => u.text).join(" "), long);
});

test("stop cancels and goes idle", () => {
  const { synth, player } = setup();
  player.start("cla/a", "Entry A", twoSections);
  const cancels = synth.cancels;
  player.stop();
  assert.ok(synth.cancels > cancels);
  assert.equal(player.state().status, "idle");
  assert.equal(player.state().key, null);
});

test("pickListenVoice prefers natural English voices", () => {
  const v = [{ name: "Fred", lang: "en-US" }, { name: "Microsoft Aria Online (Natural)", lang: "en-US" }, { name: "Amélie", lang: "fr-CA", default: true }];
  assert.equal(pickListenVoice(v).name, "Microsoft Aria Online (Natural)");
  assert.equal(pickListenVoice([{ name: "A", lang: "en-GB" }, { name: "B", lang: "en-US", default: true }]).name, "B");
  assert.equal(pickListenVoice([{ name: "Amélie", lang: "fr-CA" }]), null);
  assert.equal(pickListenVoice([]), null);
});

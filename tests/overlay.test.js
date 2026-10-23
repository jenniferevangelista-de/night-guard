// F05 + F06 for the browser overlay: a failed analysis shows "paused", and the same words from a
// different contact warn again. Runs with plain Node (node --test tests/overlay.test.js), fake DOM.
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

function el() {
  return { className: "", innerHTML: "", dataset: {}, onclick: null,
    classList: { set: new Set(), toggle(c, on) { on ? this.set.add(c) : this.set.delete(c); }, has(c) { return this.set.has(c); } },
    querySelector() { return { onclick: null }; }, querySelectorAll() { return []; }, remove() { body.splice(body.indexOf(this), 1); } };
}
const body = [];
global.window = {};
global.Audio = function () { return { play: () => Promise.resolve(), pause() {} }; };
global.document = {
  head: { appendChild() {} }, getElementById: () => null,
  body: { appendChild: e => body.push(e) },
  createElement: () => el(),
  querySelectorAll: sel => (sel === ".ng-pop" ? body.filter(e => e.className.startsWith("ng-pop")) : []),
};
global.setTimeout = f => { f(); return 0; };
global.clearTimeout = () => {};
eval(fs.readFileSync(path.join(__dirname, "..", "web", "guard-overlay.js"), "utf8"));
const tick = () => new Promise(r => setImmediate(r));
const pops = () => body.filter(e => e.className.startsWith("ng-pop"));

test("failure shows paused badge, never all clear", async () => {
  body.length = 0;
  const g = window.NightGuardLive.create({ analyze: async () => { throw new Error("offline"); } });
  g.update([{ from: "them", name: "A", text: "hi" }]);
  await tick();
  assert.ok(body[0].classList.has("ng-paused"));
  assert.match(body[0].innerHTML, /paused/);
  g.destroy();
});

test("invalid output also shows paused", async () => {
  body.length = 0;
  const g = window.NightGuardLive.create({ analyze: async () => ({ severity: "unknown", analysis_status: "invalid_output", signals: [] }) });
  g.update([{ from: "them", name: "A", text: "hi" }]);
  await tick();
  assert.ok(body[0].classList.has("ng-paused"));
  g.destroy();
});

test("same words from another contact warn again; same message does not", async () => {
  body.length = 0;
  let idx = 0;
  const res = () => ({ severity: "medium", analysis_status: "ok",
    signals: [{ id: "secrecy", message_index: idx, quote: "keep it secret", kid: "DANGER: secret" }] });
  const g = window.NightGuardLive.create({ analyze: async () => res() });
  const msgs = [{ from: "them", name: "Alex_17", text: "keep it secret" }, { from: "them", name: "Sam", text: "keep it secret" }];
  g.update(msgs); await tick();
  assert.strictEqual(pops().length, 1);
  pops()[0].remove();
  g.update(msgs); await tick();
  assert.strictEqual(pops().length, 0, "same contact, same words: no repeat");
  idx = 1;
  g.update(msgs); await tick();
  assert.strictEqual(pops().length, 1, "another contact: warned again");
  assert.ok(!body[0].classList.has("ng-paused"));
  g.destroy();
});

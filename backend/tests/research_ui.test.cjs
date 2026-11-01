// Run with node --test tests/research_ui.test.cjs; no browser or packages required.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../app/research_ui/app.js'), 'utf8');
function page(fetch) {
  const elements = {};
  for (const id of ['form', 'text', 'run', 'status', 'result', 'conclusion', 'score', 'direction', 'limitations']) {
    elements[id] = { value: '', textContent: '', hidden: false, disabled: false, children: [],
      addEventListener(_, handler) { this.submit = handler; }, setAttribute() {}, removeAttribute() {},
      replaceChildren() { this.children = []; }, appendChild(item) { this.children.push(item); } };
  }
  const document = { getElementById: id => elements[id], querySelector: () => ({ content: 'token' }),
    createElement: () => ({ textContent: '' }) };
  vm.runInNewContext(source, { document, fetch });
  return { elements, submit: () => elements.form.submit({ preventDefault() {} }) };
}
const result = { status: 'unvalidated_research_model', authorship_conclusion: 'inconclusive',
  model_diagnostic: { raw_uncalibrated_decision_score: -0.12356, positive_direction: 'toward the illustrative ai training label' },
  limitations: ['<img src=x> is text, not markup'] };
const response = data => ({ ok: true, json: async () => data });

test('validation rejects empty, whitespace and over-limit input, accepts the boundary', async () => {
  let calls = 0;
  const p = page(async () => { calls++; return response(result); });
  for (const text of ['', '   ', '!', 'x'.repeat(20001)]) {
    p.elements.text.value = text;
    await p.submit();
    assert.match(p.elements.status.textContent, /at least one letter or number/);
  }
  assert.equal(calls, 0);
  p.elements.text.value = 'x'.repeat(20000);
  await p.submit();
  assert.equal(calls, 1);
});

test('renders rounded score, direction and limitations as text without changing response', async () => {
  const p = page(async () => response(result));
  p.elements.text.value = 'fictional';
  await p.submit();
  assert.equal(p.elements.score.textContent, '-0.124');
  assert.equal(result.model_diagnostic.raw_uncalibrated_decision_score, -0.12356);
  assert.equal(p.elements.conclusion.textContent, 'INCONCLUSIVE');
  assert.match(p.elements.direction.textContent, /illustrative ai/);
  assert.equal(p.elements.limitations.children[0].textContent, result.limitations[0]);
  assert.equal(p.elements.result.hidden, false);
});

test('prevents duplicate requests and restores controls', async () => {
  let resolve, calls = 0;
  const p = page(() => { calls++; return new Promise(r => { resolve = r; }); });
  p.elements.text.value = 'fictional';
  const first = p.submit();
  assert.equal(p.elements.run.disabled, true);
  await p.submit();
  assert.equal(calls, 1);
  resolve(response(result));
  await first;
  assert.equal(p.elements.run.disabled, false);
});

test('handles unavailable server, session expiry and malformed responses without echoing input', async () => {
  for (const fetch of [async () => { throw Error('secret fictional'); },
    async () => ({ ok: false, status: 403 }), async () => response(null),
    async () => response({ ...result, model_diagnostic: { raw_uncalibrated_decision_score: 'bad' } }),
    async () => ({ ok: true, json: async () => { throw Error('bad JSON'); } })]) {
    const p = page(fetch);
    p.elements.text.value = 'secret fictional';
    await p.submit();
    assert.equal(p.elements.result.hidden, true);
    assert.ok(p.elements.status.textContent);
    assert.doesNotMatch(p.elements.status.textContent, /secret fictional/);
    assert.equal(p.elements.run.disabled, false);
  }
});

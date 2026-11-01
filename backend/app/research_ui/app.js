'use strict';

const form = document.getElementById('form');
const input = document.getElementById('text');
const button = document.getElementById('run');
const status = document.getElementById('status');
const result = document.getElementById('result');
const uploadForm = document.getElementById('upload-form');
const fileInput = document.getElementById('file');
const extractButton = document.getElementById('extract');
const artifactButton = document.getElementById('artifact-run');
const resetButton = document.getElementById('reset');
const token = document.querySelector('meta[name="csrf-token"]').content;
let pending = false;
let generation = 0;
let controller = null;

function setPending(value) {
  pending = value;
  button.disabled = value;
  artifactButton.disabled = value;
  extractButton.disabled = value;
}

resetButton.addEventListener('click', () => {
  generation++;
  if (controller) controller.abort();
  controller = null;
  setPending(false);
  input.value = '';
  fileInput.value = '';
  result.hidden = true;
  for (const id of ['conclusion', 'score', 'direction', 'model-info']) document.getElementById(id).textContent = '';
  document.getElementById('limitations').replaceChildren();
  button.textContent = 'Run Experimental Analysis';
  form.removeAttribute('aria-busy');
  status.textContent = 'Preview and results cleared from this page.';
});

uploadForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (pending) return;
  const file = fileInput.files?.[0];
  if (!file || !/\.(pdf|docx)$/i.test(file.name) || !file.size || file.size > 5 * 1024 * 1024) {
    status.textContent = 'Choose one nonempty PDF or DOCX no larger than 5 MB.';
    return;
  }
  const current = ++generation;
  controller = new AbortController();
  setPending(true);
  result.hidden = true;
  input.value = '';
  status.textContent = 'Extracting the document locally…';
  try {
    const data = new FormData();
    data.append('file', file);
    const response = await fetch('/research/extract', { method: 'POST', headers: { 'X-CSRF-Token': token },
      credentials: 'same-origin', cache: 'no-store', body: data, signal: controller.signal });
    if (current !== generation) return;
    if (!response.ok) {
      status.textContent = response.status === 403 ? 'Session expired or invalid. Reload the page and try again.' : 'Could not extract the document. Check that it is a supported, unencrypted PDF or DOCX within the limits.';
      return;
    }
    const dataResult = await response.json();
    if (current !== generation) return;
    if (typeof dataResult?.extracted_text !== 'string' || !Number.isInteger(dataResult.character_count) || dataResult.character_count < 1 || Array.from(dataResult.extracted_text).length > 20000) throw new Error('Invalid response');
    input.value = dataResult.extracted_text;
    status.textContent = 'Text extracted. Review the preview before running a diagnostic.';
  } catch {
    if (current === generation) status.textContent = 'Could not extract the document. Check that the local research server is running and try again.';
  } finally {
    if (current === generation) { controller = null; setPending(false); }
  }
});

async function run(artifact) {
  if (pending) return;
  result.hidden = true;
  const text = input.value;
  if (!text.trim() || !/[\p{L}\p{N}]/u.test(text) || Array.from(text).length > 20000) {
    status.textContent = 'Enter fictional text with at least one letter or number, up to 20,000 characters.';
    return;
  }
  const current = ++generation;
  controller = new AbortController();
  setPending(true);
  button.textContent = 'Running analysis…';
  form.setAttribute('aria-busy', 'true');
  status.textContent = 'Running the local research diagnostic…';
  try {
    const response = await fetch(artifact ? '/research/artifact-analyze' : '/research/analyze', {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token },
      credentials: 'same-origin', cache: 'no-store', body: JSON.stringify({ text }), signal: controller.signal,
    });
    if (current !== generation) return;
    if (!response.ok) {
      status.textContent = response.status === 403 ? 'Session expired or invalid. Reload the page and try again.' : artifact && response.status === 503 ? 'Trusted model unavailable. Configure a trusted fictional smoke-test artifact as described in the local demo guide, then restart the server.' : 'Unable to analyze this text. Check the input and local server, then try again.';
      return;
    }
    const data = await response.json();
    if (current !== generation) return;
    if (data?.status !== 'unvalidated_research_model' || data.authorship_conclusion !== 'inconclusive' ||
        !Number.isFinite(data.model_diagnostic?.raw_uncalibrated_decision_score) ||
        typeof data.model_diagnostic?.positive_direction !== 'string' ||
        !Array.isArray(data.limitations) || !data.limitations.length ||
        !data.limitations.every(item => typeof item === 'string' && item.trim()) ||
        (artifact && (typeof data.model_metadata?.name !== 'string' || typeof data.model_metadata?.model_version !== 'string' || data.model_metadata?.evidence_status !== 'synthetic' || !/^[a-f0-9]{64}$/.test(data.model_metadata?.artifact_sha256) || !/^[a-f0-9]{64}$/.test(data.model_metadata?.manifest_fingerprint)))) {
      status.textContent = 'The research server returned an unexpected result. Please try again.';
      return;
    }
    document.getElementById('conclusion').textContent = 'INCONCLUSIVE';
    document.getElementById('score').textContent = data.model_diagnostic.raw_uncalibrated_decision_score.toFixed(3);
    document.getElementById('direction').textContent = `Positive direction: ${data.model_diagnostic.positive_direction}.`;
    document.getElementById('model-info').textContent = artifact ? `Synthetic, unvalidated model: ${data.model_metadata.name}; version: ${data.model_metadata.model_version}; artifact SHA-256: ${data.model_metadata.artifact_sha256}; manifest fingerprint: ${data.model_metadata.manifest_fingerprint}.` : 'In-memory fictional eight-example baseline; no artifact loaded.';
    const list = document.getElementById('limitations');
    list.replaceChildren();
    for (const limitation of data.limitations) {
      const item = document.createElement('li');
      item.textContent = limitation;
      list.appendChild(item);
    }
    result.hidden = false;
    status.textContent = 'Research diagnostic complete.';
  } catch {
    if (current === generation) status.textContent = 'Could not complete the request. Check that the local research server is running and try again.';
  } finally {
    if (current === generation) {
      controller = null;
      setPending(false);
      button.textContent = 'Run Experimental Analysis';
      form.removeAttribute('aria-busy');
    }
  }
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  return run(false);
});
artifactButton.addEventListener('click', () => run(true));

'use strict';

const form = document.getElementById('form');
const input = document.getElementById('text');
const button = document.getElementById('run');
const status = document.getElementById('status');
const result = document.getElementById('result');
const token = document.querySelector('meta[name="csrf-token"]').content;
let pending = false;

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (pending) return;
  result.hidden = true;
  const text = input.value;
  if (!text.trim() || !/[\p{L}\p{N}]/u.test(text) || Array.from(text).length > 20000) {
    status.textContent = 'Enter fictional text with at least one letter or number, up to 20,000 characters.';
    return;
  }
  pending = true;
  button.disabled = true;
  button.textContent = 'Running analysis…';
  form.setAttribute('aria-busy', 'true');
  status.textContent = 'Running the local research diagnostic…';
  try {
    const response = await fetch('/research/analyze', {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token },
      credentials: 'same-origin', cache: 'no-store', body: JSON.stringify({ text }),
    });
    if (!response.ok) {
      status.textContent = response.status === 403 ? 'Session expired or invalid. Reload the page and try again.' : 'Unable to analyze this text. Check the input and local server, then try again.';
      return;
    }
    const data = await response.json();
    if (data?.status !== 'unvalidated_research_model' || data.authorship_conclusion !== 'inconclusive' ||
        !Number.isFinite(data.model_diagnostic?.raw_uncalibrated_decision_score) ||
        typeof data.model_diagnostic?.positive_direction !== 'string' ||
        !Array.isArray(data.limitations) || !data.limitations.length ||
        !data.limitations.every(item => typeof item === 'string' && item.trim())) {
      status.textContent = 'The research server returned an unexpected result. Please try again.';
      return;
    }
    document.getElementById('conclusion').textContent = 'INCONCLUSIVE';
    document.getElementById('score').textContent = data.model_diagnostic.raw_uncalibrated_decision_score.toFixed(3);
    document.getElementById('direction').textContent = `Positive direction: ${data.model_diagnostic.positive_direction}.`;
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
    status.textContent = 'Could not complete the request. Check that the local research server is running and try again.';
  } finally {
    pending = false;
    button.disabled = false;
    button.textContent = 'Run Experimental Analysis';
    form.removeAttribute('aria-busy');
  }
});

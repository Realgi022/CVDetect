// Only dynamically imported in explicitly enabled local Vite development.
const origin = 'http://127.0.0.1:8001'

export async function runLocalResearch(file: File, signal: AbortSignal): Promise<number> {
  if (window.location.origin !== 'http://127.0.0.1:5173') throw new Error('Open http://127.0.0.1:5173 for local research mode.')
  const common = { credentials: 'include' as const, cache: 'no-store' as const, signal }
  const session = await fetch(`${origin}/research/vite-session`, { ...common, method: 'POST', headers: { 'X-Research-Session': '1' } })
  if (!session.ok) throw new Error('Local research session unavailable; check the server and Vite opt-in.')
  const { csrf_token: token } = await session.json()
  if (typeof token !== 'string' || !/^[a-f0-9]{64}$/.test(token)) throw new Error('Invalid local research session response.')
  const form = new FormData(); form.append('file', file)
  const extraction = await fetch(`${origin}/research/vite-extract`, { ...common, method: 'POST', headers: { 'X-CSRF-Token': token }, body: form })
  if (!extraction.ok) throw new Error('Research extraction failed; check the document and 20,000-character limit.')
  const preview = await extraction.json()
  if (typeof preview.extracted_text !== 'string' || Array.from(preview.extracted_text).length > 20000) throw new Error('Invalid research extraction response.')
  if ((preview.extracted_text.match(/[\p{L}\p{N}]+/gu) || []).length < 20) throw new Error('Insufficient text for experimental assessment: at least 20 words are required.')
  const response = await fetch(`${origin}/research/vite-analyze`, { ...common, method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token }, body: JSON.stringify({ text: preview.extracted_text }) })
  if (!response.ok) throw new Error(response.status === 503 ? 'Trusted model unavailable; check the artifact configuration and restart the local research server.' : 'Local model inference failed.')
  const data = await response.json()
  if (data.status !== 'unvalidated_research_model' || data.authorship_conclusion !== 'inconclusive' || data.model_metadata?.evidence_status !== 'synthetic') throw new Error('Invalid local model response.')
  const score = data.model_diagnostic?.ai_class_probability
  if (score === null) throw new Error('Configured artifact does not support predict_proba; an AI-class score is unavailable.')
  if (typeof score !== 'number' || !Number.isFinite(score) || score < 0 || score > 1) throw new Error('Invalid AI-class model output.')
  return score
}

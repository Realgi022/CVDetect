import { useEffect, useRef, useState } from 'react'

type Diagnostic = {
  status: 'unvalidated_research_model'
  authorship_conclusion: 'inconclusive'
  model_metadata: { name: string; model_version: string; evidence_status: 'synthetic'; artifact_sha256: string; manifest_fingerprint: string }
  model_diagnostic: { raw_uncalibrated_decision_score: number; positive_direction: string }
  limitations: string[]
}

// This module is imported only by an explicitly enabled Vite development server.
const origin = 'http://127.0.0.1:8001'

function validateResult(value: unknown): Diagnostic {
  if (typeof value !== 'object' || value === null) throw new Error('Unexpected research response.')
  const d = value as Partial<Diagnostic>
  if (d.status !== 'unvalidated_research_model' || d.authorship_conclusion !== 'inconclusive' ||
      d.model_metadata?.evidence_status !== 'synthetic' || typeof d.model_metadata?.name !== 'string' ||
      typeof d.model_metadata?.model_version !== 'string' || !/^[a-f0-9]{64}$/.test(d.model_metadata?.artifact_sha256 || '') ||
      !/^[a-f0-9]{64}$/.test(d.model_metadata?.manifest_fingerprint || '') ||
      !Number.isFinite(d.model_diagnostic?.raw_uncalibrated_decision_score) || typeof d.model_diagnostic?.positive_direction !== 'string' ||
      !Array.isArray(d.limitations) || !d.limitations.length || !d.limitations.every(s => typeof s === 'string' && s.trim())) {
    throw new Error('Unexpected research response.')
  }
  return d as Diagnostic
}

export default function LocalResearch({ file }: { file: File }) {
  const [result, setResult] = useState<Diagnostic | null>(null)
  const [message, setMessage] = useState('')
  const [pending, setPending] = useState(false)
  const request = useRef<AbortController | null>(null)
  useEffect(() => { request.current?.abort(); setPending(false); setResult(null); setMessage(''); return () => request.current?.abort() }, [file])

  async function run() {
    if (pending || request.current) return
    if (window.location.origin !== 'http://127.0.0.1:5173') { setMessage('Open the development site at http://127.0.0.1:5173 to use local research mode.'); return }
    const controller = new AbortController()
    request.current = controller
    setPending(true); setResult(null); setMessage('Running the local research diagnostic…')
    try {
      const common = { credentials: 'include' as const, cache: 'no-store' as const, signal: controller.signal }
      const session = await fetch(`${origin}/research/vite-session`, { ...common, method: 'POST', headers: { 'X-Research-Session': '1' } })
      if (!session.ok) throw new Error('Local research session unavailable. Check that the research server and its Vite opt-in are enabled.')
      const sessionData: unknown = await session.json()
      if (typeof sessionData !== 'object' || sessionData === null || !('csrf_token' in sessionData) || typeof sessionData.csrf_token !== 'string' || !/^[a-f0-9]{64}$/.test(sessionData.csrf_token)) throw new Error('Unexpected research session response.')
      const token = sessionData.csrf_token
      const form = new FormData(); form.append('file', file)
      const extraction = await fetch(`${origin}/research/vite-extract`, { ...common, method: 'POST', headers: { 'X-CSRF-Token': token }, body: form })
      if (!extraction.ok) throw new Error(extraction.status === 403 ? 'Research session expired. Try again.' : 'Unable to extract this document for research. Use a valid PDF or DOCX within the research limits.')
      const preview: unknown = await extraction.json()
      if (typeof preview !== 'object' || preview === null || !('extracted_text' in preview) || typeof preview.extracted_text !== 'string' || !preview.extracted_text.trim() || Array.from(preview.extracted_text).length > 20000) throw new Error('Unexpected research extraction response.')
      const inference = await fetch(`${origin}/research/vite-analyze`, { ...common, method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token }, body: JSON.stringify({ text: preview.extracted_text }) })
      if (!inference.ok) throw new Error(inference.status === 503 ? 'Trusted fictional model unavailable. Check the artifact configuration and restart the research server.' : inference.status === 403 ? 'Research session expired. Try again.' : 'Unable to run the local research diagnostic.')
      const diagnostic = validateResult(await inference.json())
      if (!controller.signal.aborted) { setResult(diagnostic); setMessage('Local research diagnostic complete.') }
    } catch (error) {
      const safeMessages = new Set(['Local research session unavailable. Check that the research server and its Vite opt-in are enabled.', 'Unexpected research session response.', 'Research session expired. Try again.', 'Unable to extract this document for research. Use a valid PDF or DOCX within the research limits.', 'Unexpected research extraction response.', 'Trusted fictional model unavailable. Check the artifact configuration and restart the research server.', 'Unable to run the local research diagnostic.', 'Unexpected research response.'])
      if (!controller.signal.aborted) setMessage(error instanceof TypeError ? 'Local research server unavailable. Check that it is running and try again.' : error instanceof Error && safeMessages.has(error.message) ? error.message : 'Unable to run the local research diagnostic.')
    } finally {
      if (!controller.signal.aborted) { setPending(false); request.current = null }
    }
  }
  function reset() { request.current?.abort(); request.current = null; setPending(false); setResult(null); setMessage('Local research result cleared.') }
  return <section className="local-research" aria-labelledby="local-research-title">
    <p className="eyebrow">LOCAL RESEARCH MODE · DEVELOPMENT ONLY</p><h3 id="local-research-title">Experimental AI assessment</h3>
    <p>Fictional CVs only. This sends the selected file to the separately opted-in local research server. The model is synthetic and unvalidated; it cannot determine authorship.</p>
    <div className="local-research-actions"><button type="button" className="button button-primary" disabled={pending} onClick={() => void run()}>{pending ? 'Running local diagnostic…' : 'Run experimental AI assessment'}</button><button type="button" className="button button-secondary" onClick={reset}>Clear research result</button></div>
    <p role="status" aria-live="polite" className="feedback">{message}</p>
    {result && <div className="local-research-result"><p className="authorship-status-value">INCONCLUSIVE</p><p><strong>Raw uncalibrated decision score:</strong> {String(result.model_diagnostic.raw_uncalibrated_decision_score)}</p><p><strong>Positive direction:</strong> {result.model_diagnostic.positive_direction}</p><p>This score is not a calibrated AI-authorship probability and does not prove who wrote the CV.</p><p><strong>Model:</strong> {result.model_metadata.name} · {result.model_metadata.model_version} · synthetic, unvalidated</p><p className="research-hash"><strong>Artifact SHA-256:</strong> {result.model_metadata.artifact_sha256}<br /><strong>Manifest fingerprint:</strong> {result.model_metadata.manifest_fingerprint}</p><ul>{result.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul></div>}
  </section>
}

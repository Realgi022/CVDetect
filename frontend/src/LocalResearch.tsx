// Only dynamically imported in explicitly enabled local Vite development.
const origin = 'http://127.0.0.1:8001'

export type Chunk = { status: 'scored' | 'insufficient_text'; content_tokens: number; input_tokens: number; characters: number; ai_class_probability?: number }
export type Coverage = { source_characters: number; assigned_characters: number; scored_characters: number; source_content_tokens: number; chunk_content_tokens: number; model_input_limit: number; minimum_content_tokens: number }
export type ModelState = { status: 'loading' | 'error' | 'ready'; message?: string; score?: number; chunks?: Chunk[]; coverage?: Coverage }
export type ModelName = 'logistic' | 'roberta'

export async function runLocalResearch(file: File, signal: AbortSignal, update: (name: ModelName, state: ModelState) => void): Promise<void> {
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
  async function run(name: ModelName) {
    try {
      const response = await fetch(`${origin}/research/vite-${name === 'logistic' ? 'analyze' : 'roberta'}`, { ...common, method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token }, body: JSON.stringify({ text: preview.extracted_text }) })
      if (!response.ok) throw new Error(response.status === 503 ? `${name === 'logistic' ? 'Trusted model' : 'RoBERTa model'} unavailable; check local configuration.` : 'Local model inference failed.')
      const data = await response.json()
      if (name === 'roberta' && data.status === 'chunk_limit') throw new Error('Unable to assess — document exceeds the 16-chunk research limit.')
      if (data.status !== 'unvalidated_research_model' || data.authorship_conclusion !== 'inconclusive' || (name === 'logistic' && data.model_metadata?.evidence_status !== 'synthetic')) throw new Error('Invalid local model response.')
      if (name === 'roberta') {
        const chunks: Chunk[] = data.chunks; const coverage: Coverage = data.coverage
        const integer = (n: unknown) => typeof n === 'number' && Number.isSafeInteger(n) && n >= 0
        if (!Array.isArray(chunks) || !chunks.length || chunks.length > 16 || !coverage ||
            ![coverage.source_characters, coverage.assigned_characters, coverage.scored_characters, coverage.source_content_tokens, coverage.chunk_content_tokens, coverage.model_input_limit, coverage.minimum_content_tokens].every(integer) ||
            coverage.model_input_limit < 1 || coverage.model_input_limit > 512 || coverage.source_characters !== coverage.assigned_characters ||
            !chunks.every(c => c && integer(c.characters) && integer(c.content_tokens) && integer(c.input_tokens) && c.input_tokens <= coverage.model_input_limit && (c.status === 'insufficient_text' || (c.status === 'scored' && typeof c.ai_class_probability === 'number' && Number.isFinite(c.ai_class_probability) && c.ai_class_probability >= 0 && c.ai_class_probability <= 1))) ||
            chunks.reduce((sum, c) => sum + c.characters, 0) !== coverage.assigned_characters || chunks.reduce((sum, c) => sum + c.content_tokens, 0) !== coverage.chunk_content_tokens || chunks.reduce((sum, c) => sum + (c.status === 'scored' ? c.characters : 0), 0) !== coverage.scored_characters) throw new Error('Invalid local model response.')
        if (!signal.aborted) update(name, { status: 'ready', chunks, coverage })
        return
      }
      const score = data.model_diagnostic?.ai_class_probability
      if (score === null) throw new Error('Configured artifact does not support predict_proba; an AI-class score is unavailable.')
      if (typeof score !== 'number' || !Number.isFinite(score) || score < 0 || score > 1) throw new Error('Invalid AI-class model output.')
      if (!signal.aborted) update(name, { status: 'ready', score })
    } catch (error) {
      if (!signal.aborted) update(name, { status: 'error', message: error instanceof TypeError ? 'Local research server unavailable.' : error instanceof Error ? error.message : 'Local model inference failed.' })
    }
  }
  await Promise.all([run('logistic'), run('roberta')])
}

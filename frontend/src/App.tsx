import { useEffect, useRef, useState } from 'react'
import { checkHealth } from './health'
import { extractCv, type Extraction } from './extract'
import { analyzeCv, type Analysis } from './analyze'
import { Dashboard } from './Dashboard'

// Vite replaces this with false for every build, regardless of environment.
type LocalState = { status: 'loading' | 'error' | 'ready'; message?: string; score?: number }

type Status = 'checking' | 'connected' | 'offline'

function ConnectionStatus() {
  const [status, setStatus] = useState<Status>('checking')

  useEffect(() => {
    const controller = new AbortController()
    async function update() {
      try {
        setStatus(await checkHealth(controller.signal) ? 'connected' : 'offline')
      } catch {
        if (!controller.signal.aborted) setStatus('offline')
      }
    }
    void update()
    const interval = window.setInterval(update, 15000)
    return () => { controller.abort(); window.clearInterval(interval) }
  }, [])

  const label = { checking: 'Checking connection', connected: 'Backend connected', offline: 'Backend offline' }[status]
  return <div role="status" className="connection"><span aria-hidden="true" className={`connection-dot ${status}`} />{label}</div>
}

function UploadPreview() {
  const [loading, setLoading] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<Extraction | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [selectedName, setSelectedName] = useState('')
  const [report, setReport] = useState<Analysis | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [analysisError, setAnalysisError] = useState('')
  const [local, setLocal] = useState<LocalState | null>(null)
  const input = useRef<HTMLInputElement>(null)
  const request = useRef<AbortController | null>(null)
  useEffect(() => () => request.current?.abort(), [])

  async function upload(file: File) {
    request.current?.abort()
    setResult(null)
    setFile(null)
    setReport(null)
    setLocal(null)
    setAnalyzing(false)
    setAnalysisError('')
    setError('')
    setLoading(false)
    setSelectedName(file.name)
    if (!/\.(pdf|docx)$/i.test(file.name)) { setError('Choose a PDF or DOCX file.'); return }
    if (file.size > 5 * 1024 * 1024) { setError('File must be 5 MB or smaller.'); return }
    if (!file.size) { setError('The file is empty.'); return }
    const controller = new AbortController()
    request.current = controller
    setLoading(true)
    try {
      const extracted = await extractCv(file, controller.signal)
      if (!controller.signal.aborted) { setResult(extracted); setFile(file) }
    } catch (err) {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Unable to extract text.')
    } finally {
      if (!controller.signal.aborted) setLoading(false)
    }
  }
  async function analyze() {
    if (!file) return
    request.current?.abort()
    const controller = new AbortController()
    request.current = controller
    setAnalyzing(true)
    setAnalysisError('')
    setReport(null)
    setLocal(__LOCAL_RESEARCH_ENABLED__ ? { status: 'loading' } : null)
    if (__LOCAL_RESEARCH_ENABLED__) {
      void import('./LocalResearch').then(module => module.runLocalResearch(file, controller.signal)).then(score => {
        if (!controller.signal.aborted) setLocal({ status: 'ready', score })
      }).catch(error => {
        if (!controller.signal.aborted) setLocal({ status: 'error', message: error instanceof TypeError ? 'Local research server unavailable. Check that it is running.' : error instanceof Error ? error.message : 'Local assessment failed.' })
      })
    }
    try {
      const analysis = await analyzeCv(file, controller.signal)
      if (!controller.signal.aborted) setReport(analysis)
    } catch (err) {
      if (!controller.signal.aborted) setAnalysisError(err instanceof Error ? err.message : 'Unable to analyze this CV.')
    } finally {
      if (!controller.signal.aborted) setAnalyzing(false)
    }
  }
  return (
    <>
      <section id="upload" aria-labelledby="upload-title" className="workspace">
        <div className="workspace-heading"><div><p className="eyebrow">YOUR WORKSPACE</p><h2 id="upload-title">Start with your CV</h2><p>{__LOCAL_RESEARCH_ENABLED__ ? 'Fictional test documents only: local experimental model output is unvalidated.' : 'Preview your document and get rule-based writing and quality feedback. AI-authorship assessment is not yet available.'}</p></div><span className="step-badge">01 / UPLOAD</span></div>
        <div onDragOver={event => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); if (event.dataTransfer.files.length === 1) void upload(event.dataTransfer.files[0]); else setError('Choose exactly one file.') }} className={`dropzone ${dragging ? 'dragging' : ''}`}>
          <div aria-hidden="true" className="upload-icon">↑</div>
          <p className="drop-title">Drop your CV here, or choose a file</p>
          <p className="drop-caption">PDF or DOCX · maximum 5 MB</p>
          <input ref={input} type="file" accept=".pdf,.docx" className="sr-only" tabIndex={-1} aria-label="Choose a CV file" onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; if (file) void upload(file) }} />
          <button type="button" onClick={() => input.current?.click()} className="button button-secondary">Choose a file</button>
          <p className="privacy-note">Processed in memory by the configured backend; not saved by the application.</p>
        </div>
        {selectedName && <p className="selected-file"><strong>Selected file:</strong> <span>{selectedName}</span></p>}
        {loading && <p role="status" className="feedback">Uploading and extracting text…</p>}
        {error && <p role="alert" className="feedback error">{error}</p>}
        {result && <div className="preview"><div className="preview-heading"><div><p className="eyebrow">02 / REVIEW</p><h3>Extracted text preview</h3></div><p role="status" className="success">Text extracted · {result.character_count.toLocaleString()} characters</p></div><p className="preview-help">Check that the text was extracted correctly before analyzing.</p><div tabIndex={0} aria-label="Extracted text preview" className="preview-text">{result.extracted_text}</div></div>}
        {result && <div className="analyze-row"><button type="button" disabled={analyzing} onClick={() => void analyze()} className="button button-primary">{analyzing ? 'Preparing feedback…' : 'Analyze CV'} <span aria-hidden="true">→</span></button><p>{__LOCAL_RESEARCH_ENABLED__ ? 'Local research mode also sends the file to the experimental model.' : 'The same file is uploaded again for rule-based analysis; no AI-authorship model runs.'}</p></div>}
        {analyzing && <p role="status" className="feedback">Preparing rule-based CV feedback…</p>}
        {analysisError && <p role="alert" className="feedback error">{analysisError}</p>}
      </section>
      {report && <Dashboard report={report} local={local} />}
    </>
  )
}

export default function App() {
  return (
    <div className="app-shell">
      <header className="site-header"><div className="container header-inner"><a href="#top" className="brand"><span className="brand-mark">CV</span>CVDetect</a><nav aria-label="Main navigation" className="nav-links"><a href="#upload">Analyze CV</a><a href="#how-it-works">How it works</a></nav><ConnectionStatus /></div></header>
      <main id="top" className="container main-content">
        <section className="hero" aria-labelledby="hero-title"><div><p className="eyebrow"><span aria-hidden="true">✦</span> CV AUTHORSHIP RESEARCH</p><h1 id="hero-title">A more careful approach to <span>AI authorship in CVs.</span></h1><p className="hero-copy">{__LOCAL_RESEARCH_ENABLED__ ? 'Local development: explore an unvalidated synthetic model with fictional documents only.' : 'We’re working toward responsible AI-authorship assessment for CV writing. It is not yet validated or available; today you can preview your CV and explore separate rule-based feedback.'}</p><a href="#upload" className="button button-primary">Review your CV <span aria-hidden="true">→</span></a></div><div className="hero-aside"><p className="hero-aside-label">WHAT IS AVAILABLE TODAY</p><ol><li><span>01</span> Upload your CV</li><li><span>02</span> Check the text preview</li><li><span>03</span> Review rule-based feedback</li></ol><p>{__LOCAL_RESEARCH_ENABLED__ ? 'Experimental synthetic model output is not an authorship finding.' : <><strong>AI-authorship assessment is unavailable.</strong> No authorship model runs on your upload.</>}</p></div></section>
        <UploadPreview />
        <section id="how-it-works" className="how-section" aria-labelledby="how-title"><div className="section-heading"><p className="eyebrow">HOW IT WORKS</p><h2 id="how-title">Clear boundaries. Useful feedback.</h2></div><div className="how-grid"><div><span>01</span><h3>Authorship: not yet validated</h3><p>{__LOCAL_RESEARCH_ENABLED__ ? 'The local synthetic model is experimental and cannot prove authorship.' : 'Our future goal is responsible assessment. Writing style cannot prove authorship, and no model runs today.'}</p></div><div><span>02</span><h3>Writing observations</h3><p>Review optional, rule-based wording suggestions—not evidence of AI use.</p></div><div><span>03</span><h3>CV quality guidance</h3><p>Explore separate quality scores, not a measure of ability, hiring suitability or ATS certification.</p></div></div></section>
      </main>
      <footer className="site-footer"><div className="container">CVDetect <span>·</span> Thoughtful feedback for a clearer CV.</div></footer>
    </div>
  )
}

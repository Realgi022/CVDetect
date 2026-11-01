import { useEffect, useRef, useState } from 'react'
import { checkHealth } from './health'
import { extractCv, type Extraction } from './extract'
import { analyzeCv, type Analysis } from './analyze'
import { Dashboard } from './Dashboard'

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
  return <div role="status" className="flex items-center gap-2 text-xs font-medium text-slate-500"><span className={`h-2 w-2 rounded-full ${status === 'connected' ? 'bg-emerald-500' : status === 'offline' ? 'bg-rose-400' : 'bg-amber-400'}`} />{label}</div>
}

function UploadPreview() {
  const [loading, setLoading] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<Extraction | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [report, setReport] = useState<Analysis | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [analysisError, setAnalysisError] = useState('')
  const input = useRef<HTMLInputElement>(null)
  const request = useRef<AbortController | null>(null)
  useEffect(() => () => request.current?.abort(), [])

  async function upload(file: File) {
    request.current?.abort()
    setResult(null)
    setFile(null)
    setReport(null)
    setAnalyzing(false)
    setAnalysisError('')
    setError('')
    setLoading(false)
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
    <section aria-labelledby="upload-title" className="rounded-3xl border border-slate-200 bg-white p-5 shadow-xl shadow-slate-200/60 sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h2 id="upload-title" className="text-xl font-semibold tracking-tight text-slate-900">Your CV, ready for review</h2><p className="mt-1 text-sm text-slate-500">A little clarity for your next opportunity.</p></div>
        <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700">Text extraction</span>
      </div>
      <div onDragOver={event => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); if (event.dataTransfer.files.length === 1) void upload(event.dataTransfer.files[0]); else setError('Choose exactly one file.') }} className={`mt-7 rounded-2xl border-2 border-dashed ${dragging ? 'border-indigo-400 bg-indigo-50' : 'border-slate-200 bg-slate-50/70'} px-5 py-10 text-center`}>
        <div aria-hidden="true" className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-100 text-2xl text-indigo-700">↑</div>
        <p className="mt-5 font-semibold text-slate-800">Drop your CV here</p>
        <p className="mt-2 text-sm text-slate-500">PDF or DOCX · up to 5 MB</p>
        <input ref={input} type="file" accept=".pdf,.docx" className="sr-only" aria-label="Choose a CV file" onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; if (file) void upload(file) }} />
        <button type="button" onClick={() => input.current?.click()} className="mt-6 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white hover:bg-indigo-700">Choose a file</button>
        <p className="mt-4 text-xs text-slate-500">Your document is processed in memory and is not saved.</p>
      </div>
      {loading && <p role="status" className="mt-4 text-sm text-indigo-700">Uploading and extracting text…</p>}
      {error && <p role="alert" className="mt-4 text-sm text-rose-700">{error}</p>}
      {result && <div className="mt-6"><p role="status" className="text-sm font-semibold text-emerald-700">Text extracted successfully · {result.character_count.toLocaleString()} characters</p><h3 className="mt-4 text-sm font-semibold text-slate-900">Extracted text preview</h3><div className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-700">{result.extracted_text}</div></div>}
      {result && <button type="button" disabled={analyzing} onClick={() => void analyze()} className="mt-5 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60">{analyzing ? 'Analyzing…' : 'Analyze CV'}</button>}
      {analyzing && <p role="status" className="mt-3 text-sm text-indigo-700">Analyzing your CV…</p>}
      {analysisError && <p role="alert" className="mt-3 text-sm text-rose-700">{analysisError}</p>}
      {report && <Dashboard report={report} />}
    </section>
  )
}

export default function App() {
  return (
    <div className="min-h-screen bg-[#f8fafc] text-slate-900">
      <header className="border-b border-slate-200/80 bg-white/80"><div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-5 sm:px-8"><a href="/" className="flex items-center gap-2.5 text-lg font-bold tracking-tight"><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-sm text-white">CV</span>CVDetect</a><ConnectionStatus /></div></header>
      <main className="mx-auto max-w-6xl px-5 pb-20 pt-16 sm:px-8 sm:pt-24">
        <div className="grid items-center gap-12 lg:grid-cols-2 lg:gap-16">
          <div><span className="inline-flex rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1.5 text-xs font-semibold tracking-wide text-indigo-700">A MORE THOUGHTFUL CV</span><h1 className="mt-6 text-4xl font-bold leading-[1.1] tracking-tight sm:text-6xl">Make your next move <span className="text-indigo-600">with confidence.</span></h1><p className="mt-6 max-w-xl text-lg leading-8 text-slate-600">A clearer CV starts with better feedback. We’re building a simple way to understand and improve yours.</p><a href="#upload-title" className="mt-8 inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-3.5 text-sm font-semibold text-white shadow-lg shadow-indigo-200 hover:bg-indigo-700">Extract your CV text <span aria-hidden="true">→</span></a></div>
          <UploadPreview />
        </div>
        <div className="mt-20 grid gap-5 border-t border-slate-200 pt-10 sm:grid-cols-3">
          <div><p className="text-sm font-semibold text-slate-900">Clarity, not guesswork</p><p className="mt-2 text-sm leading-6 text-slate-500">Rule-based CV quality feedback helps you review how you communicate your experience.</p></div>
          <div><p className="text-sm font-semibold text-slate-900">Privacy in mind</p><p className="mt-2 text-sm leading-6 text-slate-500">Documents are uploaded for extraction but not saved. The preview stays on this page.</p></div>
          <div><p className="text-sm font-semibold text-slate-900">Responsible by design</p><p className="mt-2 text-sm leading-6 text-slate-500">Writing suggestions focus on clarity, not determining who wrote your CV.</p></div>
        </div>
      </main>
      <footer className="border-t border-slate-200 px-5 py-6 text-center text-xs text-slate-500">CVDetect · Built for your next chapter</footer>
    </div>
  )
}

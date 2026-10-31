import { useEffect, useState } from 'react'
import { checkHealth } from './health'

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
  return (
    <section aria-labelledby="upload-title" className="rounded-3xl border border-slate-200 bg-white p-5 shadow-xl shadow-slate-200/60 sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h2 id="upload-title" className="text-xl font-semibold tracking-tight text-slate-900">Your CV, ready for review</h2><p className="mt-1 text-sm text-slate-500">A little clarity for your next opportunity.</p></div>
        <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700">Coming soon</span>
      </div>
      <div className="mt-7 rounded-2xl border-2 border-dashed border-slate-200 bg-slate-50/70 px-5 py-10 text-center">
        <div aria-hidden="true" className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-100 text-2xl text-indigo-700">↑</div>
        <p className="mt-5 font-semibold text-slate-800">CV upload is coming soon</p>
        <p className="mt-2 text-sm text-slate-500">PDF and DOCX support is planned.</p>
        <button type="button" disabled className="mt-6 cursor-not-allowed rounded-xl bg-slate-200 px-5 py-3 text-sm font-semibold text-slate-500">Choose a file</button>
        <p className="mt-4 text-xs text-slate-500">Uploads are disabled. No files are collected or stored.</p>
      </div>
    </section>
  )
}

export default function App() {
  return (
    <div className="min-h-screen bg-[#f8fafc] text-slate-900">
      <header className="border-b border-slate-200/80 bg-white/80"><div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-5 sm:px-8"><a href="/" className="flex items-center gap-2.5 text-lg font-bold tracking-tight"><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-sm text-white">CV</span>CVDetect</a><ConnectionStatus /></div></header>
      <main className="mx-auto max-w-6xl px-5 pb-20 pt-16 sm:px-8 sm:pt-24">
        <div className="grid items-center gap-12 lg:grid-cols-2 lg:gap-16">
          <div><span className="inline-flex rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1.5 text-xs font-semibold tracking-wide text-indigo-700">A MORE THOUGHTFUL CV</span><h1 className="mt-6 text-4xl font-bold leading-[1.1] tracking-tight sm:text-6xl">Make your next move <span className="text-indigo-600">with confidence.</span></h1><p className="mt-6 max-w-xl text-lg leading-8 text-slate-600">A clearer CV starts with better feedback. We’re building a simple way to understand and improve yours.</p><a href="#upload-title" className="mt-8 inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-3.5 text-sm font-semibold text-white shadow-lg shadow-indigo-200 hover:bg-indigo-700">Explore what’s coming <span aria-hidden="true">→</span></a></div>
          <UploadPreview />
        </div>
        <div className="mt-20 grid gap-5 border-t border-slate-200 pt-10 sm:grid-cols-3">
          <div><p className="text-sm font-semibold text-slate-900">Clarity, not guesswork</p><p className="mt-2 text-sm leading-6 text-slate-500">CV quality feedback is planned to help you communicate your experience.</p></div>
          <div><p className="text-sm font-semibold text-slate-900">Privacy in mind</p><p className="mt-2 text-sm leading-6 text-slate-500">There is no upload or document storage in this initial version.</p></div>
          <div><p className="text-sm font-semibold text-slate-900">Responsible by design</p><p className="mt-2 text-sm leading-6 text-slate-500">AI-writing detection is experimental and cannot reliably identify who wrote a text.</p></div>
        </div>
      </main>
      <footer className="border-t border-slate-200 px-5 py-6 text-center text-xs text-slate-500">CVDetect · Built for your next chapter</footer>
    </div>
  )
}

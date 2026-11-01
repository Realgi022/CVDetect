import type { Analysis } from './analyze'

const labels: Record<string, [string, string]> = {
  structure: ['Structure', '30%'], experience: ['Experience / projects', '30%'],
  skills: ['Skills', '20%'], readability: ['Readability', '20%'],
}

export function Dashboard({ report }: { report: Analysis }) {
  const groups = [
    { title: 'Strengths', description: 'What the rules recognized', items: report.strengths, tone: 'border-emerald-200 bg-emerald-50/60', marker: 'text-emerald-700', icon: '✓' },
    { title: 'Improvement opportunities', description: 'Areas to review in your CV', items: report.weaknesses, empty: report.recommendations.length ? 'See the recommendations below for suggested improvements.' : 'None identified by these rules.', tone: 'border-amber-200 bg-amber-50/50', marker: 'text-amber-800', icon: '!' },
    { title: 'Actionable recommendations', description: 'Consider these next steps', items: report.recommendations, tone: 'border-indigo-200 bg-indigo-50/50', marker: 'text-indigo-700', icon: '→' },
  ]
  return <section aria-labelledby="analysis-title" className="mt-8 overflow-hidden rounded-2xl border border-indigo-100 bg-white shadow-lg shadow-indigo-100/50">
    <div className="bg-gradient-to-br from-indigo-700 to-violet-800 p-6 text-white sm:p-8">
      <p role="status" className="text-xs font-semibold uppercase tracking-widest text-indigo-100">Analysis complete · Rule-based guidance</p>
      <div className="mt-4 flex flex-wrap items-end justify-between gap-5">
        <div><h3 id="analysis-title" className="text-2xl font-bold tracking-tight">Your CV quality overview</h3><p className="mt-2 max-w-md text-sm leading-6 text-indigo-100">A starting point for reviewing how your experience is presented, not a measure of your ability.</p></div>
        <div aria-label={`Overall score ${report.overall_score} out of 100`}><span className="text-5xl font-bold tracking-tight">{report.overall_score}</span><span className="text-lg text-indigo-100"> / 100</span><p className="mt-1 text-xs font-medium text-indigo-100">Overall score</p></div>
      </div>
    </div>
    <div className="p-5 sm:p-7">
      <h4 className="text-sm font-bold text-slate-900">Score breakdown</h4>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">{Object.entries(report.categories).map(([key, item]) => <div key={key} className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
        <div className="flex items-start justify-between gap-2"><div><p className="text-sm font-semibold text-slate-900">{labels[key]?.[0] || key}</p><p className="mt-1 text-xs text-slate-600">{labels[key]?.[1]} of overall</p></div><span className="text-sm font-bold text-indigo-700">{item.score}<span className="font-normal text-slate-600"> / 100</span></span></div>
        <div role="progressbar" aria-label={`${labels[key]?.[0] || key} score`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={item.score} className="mt-4 h-2 overflow-hidden rounded-full bg-indigo-100"><div className="h-full rounded-full bg-indigo-600" style={{ width: `${item.score}%` }} /></div>
        <details className="mt-3 text-sm leading-6 text-slate-600"><summary className="cursor-pointer font-semibold text-indigo-700">How this is scored</summary><p className="mt-2 break-words">{item.explanation}</p></details>
      </div>)}</div>
      <div className="mt-6 grid gap-4">{groups.map(group => <section key={group.title} className={`rounded-xl border p-4 sm:p-5 ${group.tone}`}><div className="flex items-start gap-3"><span aria-hidden="true" className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white font-bold ${group.marker}`}>{group.icon}</span><div className="min-w-0"><h4 className="font-bold text-slate-900">{group.title}</h4><p className="mt-0.5 text-xs text-slate-600">{group.description}</p>{group.items.length ? <ul className="mt-3 list-disc space-y-3 break-words pl-4 text-sm leading-6 text-slate-700">{group.items.map((item, i) => <li key={i}>{item}</li>)}</ul> : <p className="mt-3 text-sm text-slate-600">{group.empty || 'None identified by these rules.'}</p>}</div></div></section>)}</div>
      <details className="mt-6 border-t border-slate-200 pt-4 text-sm leading-6 text-slate-600"><summary className="cursor-pointer font-semibold text-indigo-700">About this analysis and its limitations</summary><p className="mt-2">{report.method}</p></details>
    </div>
  </section>
}

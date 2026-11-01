import type { Analysis } from './analyze'

const labels: Record<string, string> = { structure: 'Structure / sections · 30%', experience: 'Experience / projects · 30%', skills: 'Skills · 20%', readability: 'Readability / clarity · 20%' }

export function Dashboard({ report }: { report: Analysis }) {
  return <section aria-labelledby="analysis-title" className="mt-6 rounded-2xl border border-indigo-100 bg-indigo-50/50 p-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 id="analysis-title" className="text-lg font-semibold">CV quality guidance</h3><p role="status" className="mt-1 text-sm text-emerald-700">Analysis complete</p></div><p className="text-3xl font-bold text-indigo-700">{report.overall_score}<span className="text-sm font-medium text-slate-500"> / 100</span></p></div>
    <div className="mt-5 grid gap-3 sm:grid-cols-2">{Object.entries(report.categories).map(([key, item]) => <div key={key} className="rounded-xl border border-slate-200 bg-white p-4"><div className="flex justify-between gap-2 text-sm font-semibold"><span>{labels[key] || key}</span><span className="text-indigo-700">{item.score}/100</span></div><p className="mt-2 text-xs leading-5 text-slate-600">{item.explanation}</p></div>)}</div>
    {([['Strengths', report.strengths], ['Weaknesses', report.weaknesses], ['Recommendations', report.recommendations]] as const).map(([title, items]) => <div key={title} className="mt-5"><h4 className="text-sm font-semibold">{title}</h4>{items.length ? <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-600">{items.map((item, i) => <li key={i}>{item}</li>)}</ul> : <p className="mt-2 text-sm text-slate-500">None identified by these rules.</p>}</div>)}
    <p className="mt-5 border-t border-indigo-100 pt-4 text-xs leading-5 text-slate-600">{report.method}</p>
  </section>
}

import type { Analysis } from './analyze'

const labels: Record<string, [string, string]> = {
  structure: ['Structure', '30%'], experience: ['Experience / projects', '30%'],
  skills: ['Skills', '20%'], readability: ['Readability', '20%'],
}

const insightLabels: Record<string, string> = {
  generic_phrase: 'Generic phrase', vague_description: 'Clarify a contribution', repeated_opening: 'Repeated bullet opening',
}

export function Dashboard({ report }: { report: Analysis }) {
  const groups = [
    { title: 'Strengths', description: 'What the rules recognized', items: report.strengths, icon: '✓', tone: 'strength' },
    { title: 'Improvement opportunities', description: 'Areas to review in your CV', items: report.weaknesses, empty: report.recommendations.length ? 'See the recommendations below for suggested improvements.' : 'None identified by these rules.', icon: '!', tone: 'opportunity' },
    { title: 'Recommendations', description: 'Consider these next steps', items: report.recommendations, icon: '→', tone: 'recommendation' },
  ]
  return <section aria-labelledby="analysis-title" className="dashboard">
    <div className="report-heading"><div><p role="status" className="eyebrow">03 / ANALYSIS COMPLETE</p><h2 id="analysis-title">Your CV quality overview</h2><p>Explore your results and decide what is useful for your CV.</p></div><span className="step-badge">RULE-BASED GUIDANCE</span></div>
    <div className="score-overview"><div className="overall-score"><p>Overall quality score</p><div aria-label={`Overall score ${report.overall_score} out of 100`}><strong>{report.overall_score}</strong><span> / 100</span></div><p>Weighted score across four categories</p></div><div className="score-context"><p className="eyebrow">UNDERSTANDING YOUR SCORE</p><h3>Feedback, not a final judgment.</h3><p>This score is heuristic guidance for reviewing presentation. It is not a measure of your ability, hiring suitability, or ATS certification.</p></div></div>
    <div className="report-section"><div className="section-title"><div><p className="eyebrow">THE BREAKDOWN</p><h3>Scores by category</h3></div><p>Expand each card to see how it is scored.</p></div>
      <div className="category-grid">{Object.entries(report.categories).map(([key, item]) => <div key={key} className="category-card">
        <div className="category-top"><div><h4>{labels[key]?.[0] || key}</h4><p>{labels[key]?.[1]} of overall</p></div><p className="category-score">{item.score}<span> / 100</span></p></div>
        <div role="progressbar" aria-label={`${labels[key]?.[0] || key} score`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={item.score} className="progress-track"><div className="progress-fill" style={{ width: `${item.score}%` }} /></div>
        <details><summary>How this is scored</summary><p>{item.explanation}</p></details>
      </div>)}</div>
    </div>
    <div className="report-section"><div className="section-title"><div><p className="eyebrow">YOUR FEEDBACK</p><h3>Where to focus</h3></div><p>Use these observations in the context of your experience.</p></div>
      <div className="feedback-grid">{groups.map(group => <section key={group.title} className="feedback-card"><span aria-hidden="true" className={`feedback-icon ${group.tone}`}>{group.icon}</span><h4>{group.title}</h4><p className="card-subtitle">{group.description}</p>{group.items.length ? <ul>{group.items.map((item, i) => <li key={i}>{item}</li>)}</ul> : <p className="empty-text">{group.empty || 'None identified by these rules.'}</p>}</section>)}</div>
    </div>
    {report.writing_insights != null && <section aria-labelledby="writing-insights-title" className="writing-section"><div className="section-title"><div><p className="eyebrow">OPTIONAL SUGGESTIONS</p><h3 id="writing-insights-title">Writing Insights</h3><p>Wording suggestions are separate from your score. Use only what fits your experience.</p></div></div>
      {report.writing_insights.length ? <ul className="insight-grid">{report.writing_insights.map(insight => <li key={insight.id} className="insight-card"><h4>{insightLabels[insight.type] || 'Wording suggestion'}</h4><p>{insight.explanation}</p><p><strong>Consider: </strong>{insight.recommendation}</p></li>)}</ul> : <p className="insight-empty">No wording suggestions were found by these rules. You can still review your CV for clarity and context.</p>}
      <p className="writing-disclaimer">These limited rules can miss issues or flag acceptable wording. They do not determine who wrote the text.</p>
    </section>}
    <details className="method-details"><summary>About this analysis and its limitations</summary><p>{report.method}</p></details>
  </section>
}

import type { Analysis } from './analyze'

const labels: Record<string, [string, string]> = {
  structure: ['Structure', '30%'], experience: ['Experience / projects', '30%'],
  skills: ['Skills', '20%'], readability: ['Readability', '20%'],
}

const insightLabels: Record<string, string> = {
  generic_phrase: 'Generic phrase', vague_description: 'Clarify a contribution', repeated_opening: 'Repeated bullet opening',
}

// This is a product-availability state, not an API result or model prediction.
function AuthorshipAvailability() {
  return <section className="authorship-panel" aria-labelledby="authorship-title">
    <div className="authorship-heading"><div><p className="eyebrow">AI AUTHORSHIP ASSESSMENT</p><h3 id="authorship-title">Authorship cannot be determined</h3></div><span className="availability-badge">NOT YET VALIDATED</span></div>
    <div className="authorship-status"><p className="authorship-status-label">Assessment status</p><p className="authorship-status-value">INCONCLUSIVE</p><p>Unavailable — no AI-authorship model was run on this CV.</p></div>
    <p className="authorship-explanation">AI-authorship assessment is still under development and is not available in the public product. This is a placeholder, not a model inference or a finding about your document.</p>
    <p className="authorship-caution">Writing style alone cannot prove who wrote a CV. Mistaken authorship claims can harm people and must not be used for hiring decisions.</p>
  </section>
}

export function Dashboard({ report }: { report: Analysis }) {
  const groups = [
    { title: 'Strengths', description: 'What the rules recognized', items: report.strengths, icon: '✓', tone: 'strength' },
    { title: 'Improvement opportunities', description: 'Areas to review in your CV', items: report.weaknesses, empty: report.recommendations.length ? 'See the recommendations below for suggested improvements.' : 'None identified by these rules.', icon: '!', tone: 'opportunity' },
    { title: 'Recommendations', description: 'Consider these next steps', items: report.recommendations, icon: '→', tone: 'recommendation' },
  ]
  return <section aria-labelledby="analysis-title" className="dashboard">
    <div className="report-heading"><div><p role="status" className="eyebrow">03 / REVIEW COMPLETE</p><h2 id="analysis-title">Your CV review</h2><p>See the current authorship assessment status and your separate rule-based feedback.</p></div><span className="step-badge">CV REVIEW</span></div>
    <AuthorshipAvailability />
    {report.writing_insights != null && <section aria-labelledby="writing-insights-title" className="writing-section"><div className="section-title"><div><p className="eyebrow">RULE-BASED · NOT AUTHORSHIP EVIDENCE</p><h3 id="writing-insights-title">Writing observations</h3><p>Writing Insights offers optional wording suggestions, separate from authorship assessment and your quality score. Use only what fits your experience.</p></div></div>
      {report.writing_insights.length ? <ul className="insight-grid">{report.writing_insights.map(insight => <li key={insight.id} className="insight-card"><h4>{insightLabels[insight.type] || 'Wording suggestion'}</h4><p>{insight.explanation}</p><p><strong>Consider: </strong>{insight.recommendation}</p></li>)}</ul> : <p className="insight-empty">No wording suggestions were found by these rules. You can still review your CV for clarity and context.</p>}
      <p className="writing-disclaimer">These limited rules can miss issues or flag acceptable wording. They do not determine who wrote the text or indicate AI use.</p>
    </section>}
    <details className="quality-details"><summary><span><span className="eyebrow">OPTIONAL · RULE-BASED</span><strong>Your CV quality overview</strong><span>View your score, breakdown and recommendations</span></span><span className="quality-toggle" aria-hidden="true">+</span></summary>
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
    <details className="method-details"><summary>About this analysis and its limitations</summary><p>{report.method}</p></details>
    </details>
  </section>
}

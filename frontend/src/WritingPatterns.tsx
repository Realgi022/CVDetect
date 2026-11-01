import type { WritingPatterns as Patterns } from './analyze'

export function WritingPatterns({ data }: { data: Patterns }) {
  const { coverage, sentence_length: lengths, repetition, generic_phrases: generic, specificity } = data
  return <section className="patterns-section" aria-labelledby="patterns-title">
    <div className="section-title"><div><p className="eyebrow">COMPUTED FROM YOUR EXTRACTED TEXT</p><h3 id="patterns-title">Writing patterns</h3><p>Descriptive measurements, not AI-authorship evidence or probabilities.</p></div></div>
    <p className="patterns-coverage">{coverage.units} text units · {coverage.words} words · {coverage.included_lines} of {coverage.nonempty_lines} nonempty lines included</p>
    {coverage.truncated && <p className="patterns-notice">Only the first {coverage.analyzed_characters.toLocaleString()} of {coverage.total_characters.toLocaleString()} extracted characters were analyzed for these patterns; the last fragment may be cut off.</p>}
    {data.status === 'insufficient' && <p className="patterns-notice">Limited text: fewer than {coverage.minimum_words} words or {coverage.minimum_units} units were recognized. Counts are shown where available, but variation may not be meaningful.</p>}
    <div className="patterns-grid">
      <section className="pattern-card"><h4>Unit length distribution</h4><p>Words per recognized sentence or line fragment, including bullets. Counts are out of {coverage.units} units.</p>
        {coverage.units ? <ul className="distribution">{lengths.distribution.map(bucket => <li key={bucket.label}><div><span>{bucket.label}</span><strong>{bucket.count} / {coverage.units}</strong></div><progress aria-label={`${bucket.label}: ${bucket.count} of ${coverage.units} units`} max={coverage.units} value={bucket.count} /></li>)}</ul> : <p className="pattern-empty">No countable text units found.</p>}
        <p className="pattern-detail">Mean: {lengths.mean_words === null ? 'unavailable' : `${lengths.mean_words} words`}. Population standard deviation: {lengths.population_stddev_words === null ? 'unavailable' : `${lengths.population_stddev_words} words`}.</p>
      </section>
      <section className="pattern-card"><h4>Repeated wording</h4><p>Two-word sequences appearing in at least two different units: <strong>{repetition.repeated_two_word_phrases}</strong> distinct sequences.</p><p><strong>{repetition.units_with_repeated_opening} / {repetition.units_with_two_word_opening}</strong> units with at least two words share their first two words with another unit ({repetition.repeated_opening_groups} opening groups).</p><p className="pattern-detail">Counts include common wording and do not assess authorship. Repeated text is not returned.</p></section>
      <section className="pattern-card"><h4>Listed professional phrases</h4><p><strong>{generic.units_with_match} / {coverage.units}</strong> units contain at least one phrase from a small fixed list.</p>{generic.matched.length ? <ul className="pattern-list">{generic.matched.map(item => <li key={item.phrase}>“{item.phrase}” — {item.unit_count} {item.unit_count === 1 ? 'unit' : 'units'}</li>)}</ul> : <p className="pattern-empty">No listed phrases recognized.</p>}<p className="pattern-detail">A match can be appropriate and is not evidence of AI use.</p></section>
      <section className="pattern-card"><h4>Specificity indicators</h4><p>Counts out of {coverage.units} units:</p><ul className="pattern-list"><li><strong>{specificity.units_with_number}</strong> contain a numeric digit.</li><li><strong>{specificity.units_with_measurable_pattern}</strong> contain a number followed by a listed measure, such as users, hours or percent.</li><li><strong>{specificity.units_starting_action_verb}</strong> start with a listed action verb.</li></ul><p className="pattern-detail">These patterns do not verify outcomes; numbers are optional and qualitative detail can matter too.</p></section>
    </div>
    <p className="patterns-limitations">{data.limitations} Contact-like and labeled personal lines and recognized headings are excluded; other identifying content may remain in the analysis.</p>
  </section>
}

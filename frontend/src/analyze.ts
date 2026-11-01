import { apiUrl } from './health'

export type WritingInsight = {
  id: string
  type: string
  priority: string
  explanation: string
  recommendation: string
}

export type WritingPatterns = {
  status: 'sufficient' | 'insufficient'
  coverage: { total_characters: number; analyzed_characters: number; truncated: boolean; nonempty_lines: number; included_lines: number; units: number; words: number; minimum_words: number; minimum_units: number }
  sentence_length: { distribution: { label: string; count: number }[]; mean_words: number | null; population_stddev_words: number | null }
  repetition: { repeated_two_word_phrases: number; repeated_opening_groups: number; units_with_repeated_opening: number; units_with_two_word_opening: number }
  generic_phrases: { matched: { phrase: string; unit_count: number }[]; units_with_match: number }
  specificity: { units_with_number: number; units_with_measurable_pattern: number; units_starting_action_verb: number }
  limitations: string
}

export type Analysis = {
  overall_score: number
  categories: Record<string, { score: number; explanation: string }>
  strengths: string[]
  weaknesses: string[]
  recommendations: string[]
  method: string
  writing_insights?: WritingInsight[]
  writing_patterns?: WritingPatterns
}

export async function analyzeCv(file: File, signal: AbortSignal): Promise<Analysis> {
  const form = new FormData()
  form.append('file', file)
  let response: Response
  try {
    response = await fetch(`${apiUrl}/api/cv/analyze`, { method: 'POST', body: form, signal })
  } catch (error) {
    if (signal.aborted) throw error
    throw new Error('Could not connect to the backend. Check that it is running and try again.')
  }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    const detail = typeof body === 'object' && body !== null && 'detail' in body ? body.detail : null
    throw new Error(typeof detail === 'string' ? detail : 'Unable to analyze this CV. Please try again.')
  }
  return response.json() as Promise<Analysis>
}

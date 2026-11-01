import { apiUrl } from './health'

export type WritingInsight = {
  id: string
  type: string
  priority: string
  explanation: string
  recommendation: string
}

export type Analysis = {
  overall_score: number
  categories: Record<string, { score: number; explanation: string }>
  strengths: string[]
  weaknesses: string[]
  recommendations: string[]
  method: string
  writing_insights?: WritingInsight[]
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

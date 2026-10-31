import { apiUrl } from './health'

export type Extraction = { filename: string; file_type: string; character_count: number; extracted_text: string }

export async function extractCv(file: File, signal: AbortSignal): Promise<Extraction> {
  const form = new FormData()
  form.append('file', file)
  let response: Response
  try {
    response = await fetch(`${apiUrl}/api/cv/extract`, { method: 'POST', body: form, signal })
  } catch (error) {
    if (signal.aborted) throw error
    throw new Error('Could not connect to the backend. Check that it is running and try again.')
  }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    const detail = typeof body === 'object' && body !== null && 'detail' in body ? body.detail : null
    throw new Error(typeof detail === 'string' ? detail : 'Unable to extract text. Please try again.')
  }
  return response.json() as Promise<Extraction>
}

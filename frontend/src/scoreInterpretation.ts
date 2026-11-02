/** Illustrative bands for an uncalibrated AI-class output in the range [0, 1]. */
export function interpretAiClassScore(score: number): { title: string; explanation: string } | null {
  if (!Number.isFinite(score) || score < 0 || score > 1) return null
  if (score < 0.25) return {
    title: 'LOW AI SIGNAL',
    explanation: 'The model strongly favors human-written text for this section. However, this does not rule out AI assistance, and the result cannot confirm human authorship.',
  }
  if (score < 0.5) return {
    title: 'UNCERTAIN AI SIGNAL',
    explanation: 'The model leans toward human-written text, but its output cannot reliably establish whether AI was involved.',
  }
  if (score < 0.75) return {
    title: 'ELEVATED AI SIGNAL',
    explanation: 'The model favors AI-generated text for this section. However, this result is not proof of AI use and should not be treated as a definitive judgment.',
  }
  return {
    title: 'HIGH AI SIGNAL',
    explanation: 'The model strongly favors AI-generated text for this section. However, human-written content can also receive high scores, so this result alone cannot establish authorship.',
  }
}

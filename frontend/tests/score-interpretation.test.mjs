import { test } from 'node:test'
import assert from 'node:assert/strict'
import { interpretAiClassScore } from '../src/scoreInterpretation.ts'

test('decimal score boundaries map to the specified interpretation bands', () => {
  for (const [score, title] of [[0, 'LOW AI SIGNAL'], [0.249, 'LOW AI SIGNAL'], [0.25, 'UNCERTAIN AI SIGNAL'], [0.499, 'UNCERTAIN AI SIGNAL'], [0.5, 'ELEVATED AI SIGNAL'], [0.749, 'ELEVATED AI SIGNAL'], [0.75, 'HIGH AI SIGNAL'], [1, 'HIGH AI SIGNAL']]) {
    assert.equal(interpretAiClassScore(score)?.title, title, `score ${score}`)
    assert.ok(interpretAiClassScore(score)?.explanation)
  }
})

test('invalid values never receive an interpretation', () => {
  for (const score of [-0.001, 1.001, NaN, Infinity, -Infinity]) assert.equal(interpretAiClassScore(score), null)
})

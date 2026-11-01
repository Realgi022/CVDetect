// Run after a production build, including one made with VITE_LOCAL_RESEARCH=1.
import { readdir, readFile } from 'node:fs/promises'
import { join } from 'node:path'
import assert from 'node:assert/strict'

async function files(path) {
  const entries = await readdir(path, { withFileTypes: true })
  const nested = await Promise.all(entries.map(e => e.isDirectory() ? files(join(path, e.name)) : [join(path, e.name)]))
  return nested.flat()
}
for (const path of await files('dist')) {
  const content = await readFile(path, 'utf8')
  assert.doesNotMatch(content, /\/research\/vite-(session|extract|analyze)|Run experimental AI assessment|unvalidated_research_model/)
}
console.log('Production bundle contains no local research integration or endpoints.')

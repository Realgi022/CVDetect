// Real local services and a fictional DOCX required; see docs/local_research_demo.md.
import { spawn } from 'node:child_process'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import assert from 'node:assert/strict'

const file = process.env.CVDETECT_TEST_DOCX
assert.ok(file, 'Set CVDETECT_TEST_DOCX to a fictional DOCX path.')
const second = process.env.CVDETECT_TEST_DOCX_2
assert.ok(second, 'Set CVDETECT_TEST_DOCX_2 to a second fictional DOCX path.')
const longFile = process.env.CVDETECT_TEST_DOCX_LONG
const documents = await Promise.all([file, second, ...(longFile ? [longFile] : [])].map(async path => (await readFile(path)).toString('base64')))
const mocked = process.env.CVDETECT_MOCK_RESEARCH === '1'
const profile = await mkdtemp(join(tmpdir(), 'cvdetect-real-browser-'))
const chrome = process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const browser = spawn(chrome, ['--headless=new', '--disable-gpu', '--no-first-run', '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' })
const wait = ms => new Promise(resolve => setTimeout(resolve, ms))
let socket
try {
  let port
  for (let i = 0; i < 100 && !port; i++) {
    try { port = Number((await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]) } catch { await wait(100) }
  }
  assert.ok(port, 'Chrome did not start')
  const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json()
  socket = new WebSocket(targets.find(t => t.type === 'page').webSocketDebuggerUrl)
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject })
  let id = 0
  const pending = new Map()
  socket.onmessage = event => { const m = JSON.parse(event.data); if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.reject(Error(m.error.message)) : p.resolve(m.result) } }
  const send = (method, params = {}) => new Promise((resolve, reject) => { const n = ++id; pending.set(n, { resolve, reject }); socket.send(JSON.stringify({ id: n, method, params })) })
  const evaluate = async expression => { const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true }); if (r.exceptionDetails) throw Error(r.exceptionDetails.text); return r.result.value }
  await send('Page.enable')
  await send('Page.addScriptToEvaluateOnNewDocument', { source: `
    window.researchResponse = null; window.robertaResponse = null;
    window.mockResearch = ${JSON.stringify(mocked)}; window.robertaMode = 'ready';
    const nativeFetch = window.fetch;
    window.fetch = async (...args) => {
      const url = String(args[0]); let r;
      if (window.mockResearch && url.endsWith('/research/vite-session')) r = new Response(JSON.stringify({csrf_token:'a'.repeat(64)}));
      else if (window.mockResearch && url.endsWith('/research/vite-extract')) r = new Response(JSON.stringify({extracted_text:window.robertaMode === 'short' ? 'fictional' : 'fictional '.repeat(30)}));
      else if (window.mockResearch && url.endsWith('/research/vite-analyze')) r = window.robertaMode === 'logisticerror' ? new Response('{}',{status:503}) : new Response(JSON.stringify({status:'unvalidated_research_model',authorship_conclusion:'inconclusive',model_metadata:{evidence_status:'synthetic'},model_diagnostic:{ai_class_probability:0.314}}));
      else if (window.mockResearch && url.endsWith('/research/vite-roberta')) r = window.robertaMode === 'error' ? new Response('{}',{status:503}) : new Response(JSON.stringify(window.robertaMode === 'long' ? {status:'chunk_limit',max_chunks:16} : {status:'unvalidated_research_model',authorship_conclusion:'inconclusive',chunks:[{status:'scored',content_tokens:30,input_tokens:32,characters:300,ai_class_probability:0.826},{status:'insufficient_text',content_tokens:3,input_tokens:5,characters:20}],coverage:{source_characters:320,assigned_characters:320,scored_characters:300,source_content_tokens:33,chunk_content_tokens:33,model_input_limit:512,minimum_content_tokens:10}}));
      else r = await nativeFetch(...args);
      if (url.endsWith('/research/vite-analyze') && r.ok) window.researchResponse = await r.clone().json(); if (url.endsWith('/research/vite-roberta') && r.ok) window.robertaResponse = await r.clone().json(); return r;
    };
  ` })
  await send('Page.navigate', { url: 'http://127.0.0.1:5173/' })
  for (let i = 0; i < 100 && !await evaluate('!!document.querySelector(".dropzone")'); i++) await wait(100)
  for (const [index, bytes] of documents.entries()) {
    await evaluate(`window.researchResponse = null; window.robertaResponse = null; (() => { const bytes = Uint8Array.from(atob(${JSON.stringify(bytes)}), c => c.charCodeAt(0)); const d = new DataTransfer(); d.items.add(new File([bytes], 'fictional.docx', {type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'})); document.querySelector('.dropzone').dispatchEvent(new DragEvent('drop', {bubbles:true, dataTransfer:d})); })()`)
    for (let i = 0; i < 100 && !await evaluate('!!document.querySelector(".analyze-row button")'); i++) await wait(100)
    await evaluate(`document.querySelector('.analyze-row button').click()`)
    for (let i = 0; i < 600 && !await evaluate('!!window.researchResponse && !!window.robertaResponse && !!document.querySelector(".chunk-results")'); i++) await wait(100)
    const result = await evaluate(`({text:document.querySelector('[data-model="logistic"]')?.innerText, score:window.researchResponse?.model_diagnostic.ai_class_probability, robertaText:document.querySelector('[data-model="roberta"]')?.innerText, chunks:window.robertaResponse?.chunks, coverage:window.robertaResponse?.coverage})`)
    assert.equal(typeof result.score, 'number', JSON.stringify(result))
    assert.ok(result.text.includes((result.score * 100).toFixed(1) + '%'), JSON.stringify(result))
    assert.ok(Array.isArray(result.chunks) && result.chunks.length, JSON.stringify(result))
    if (!mocked && index === 2) assert.ok(result.chunks.length > 1, 'Long fictional CV should produce multiple chunks')
    for (const [i, chunk] of result.chunks.entries()) if (chunk.status === 'scored') {
      const text = await evaluate(`document.querySelectorAll('.chunk-results li')[${i}].innerText`)
      assert.ok(text.includes((chunk.ai_class_probability * 100).toFixed(1) + '%'), JSON.stringify(result))
      const title = chunk.ai_class_probability < 0.25 ? 'LOW AI SIGNAL' : chunk.ai_class_probability < 0.5 ? 'UNCERTAIN AI SIGNAL' : chunk.ai_class_probability < 0.75 ? 'ELEVATED AI SIGNAL' : 'HIGH AI SIGNAL'
      assert.ok(text.includes(title), `Missing interpretation for chunk ${i + 1}`)
    }
    assert.equal(result.coverage.source_characters, result.coverage.assigned_characters)
    assert.match(result.robertaText, /No overall RoBERTa score/)
    assert.match(result.robertaText, /interpretation bands are illustrative and have not been scientifically validated on CVs/i)
    if (mocked) {
      assert.match(result.robertaText, /82\.6%[\s\S]*HIGH AI SIGNAL[\s\S]*human-written content can also receive high scores/i)
      assert.equal(await evaluate(`document.querySelectorAll('.chunk-results li')[1].querySelector('.chunk-interpretation') === null`), true)
      assert.equal(await evaluate(`document.querySelector('[data-model="logistic"] .chunk-interpretation') === null`), true)
    }
    if (!mocked && index === 2) console.log(`Long fictional CV: ${result.chunks.length} chunks, ${result.coverage.assigned_characters}/${result.coverage.source_characters} characters assigned, ${result.coverage.source_content_tokens} source tokens; displayed chunk scores match backend.`)
    for (const width of [1440, 768, 390, 320]) {
      await send('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: false })
      assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'), true, `overflow at ${width}px`)
    }
  }
  if (mocked) {
    for (const [mode, expected] of [['long', 'Unable to assess — document exceeds the 16-chunk research limit'], ['error', 'RoBERTa model unavailable']]) {
      await evaluate(`window.robertaMode = ${JSON.stringify(mode)}; document.querySelector('.analyze-row button').click()`)
      for (let i = 0; i < 100 && !await evaluate(`document.querySelector('[data-model="roberta"]')?.innerText.includes(${JSON.stringify(expected)})`); i++) await wait(100)
      assert.match(await evaluate(`document.querySelector('[data-model="roberta"]').innerText`), new RegExp(expected))
      assert.match(await evaluate(`document.querySelector('[data-model="logistic"]').innerText`), /31\.4%/)
    }
    await evaluate(`window.robertaMode = 'short'; document.querySelector('.analyze-row button').click()`)
    for (let i = 0; i < 100 && !await evaluate(`document.querySelector('[data-model="roberta"]')?.innerText.includes('Insufficient text')`); i++) await wait(100)
    assert.match(await evaluate(`document.querySelector('[data-model="roberta"]').innerText`), /Insufficient text/)
    assert.match(await evaluate(`document.querySelector('[data-model="logistic"]').innerText`), /Insufficient text/)
    await evaluate(`window.robertaMode = 'logisticerror'; document.querySelector('.analyze-row button').click()`)
    for (let i = 0; i < 100 && !await evaluate(`document.querySelector('[data-model="roberta"]')?.innerText.includes('82.6%')`); i++) await wait(100)
    assert.match(await evaluate(`document.querySelector('[data-model="logistic"]').innerText`), /Trusted model unavailable/)
    assert.match(await evaluate(`document.querySelector('[data-model="roberta"]').innerText`), /82\.6%/)
  }
  console.log(mocked ? 'Mocked local browser: both scores, independent errors, chunk limit and responsive widths passed.' : 'Fictional CVs: displayed scores match real backend output; responsive widths passed.')
} finally {
  socket?.close()
  browser.kill()
  await new Promise(resolve => { if (browser.exitCode !== null) resolve(); else browser.once('exit', resolve) })
  await rm(profile, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 })
}

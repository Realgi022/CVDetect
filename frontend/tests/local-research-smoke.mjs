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
const documents = await Promise.all([file, second].map(async path => (await readFile(path)).toString('base64')))
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
    window.researchResponse = null;
    const nativeFetch = window.fetch;
    window.fetch = async (...args) => { const r = await nativeFetch(...args); if (String(args[0]).endsWith('/research/vite-analyze') && r.ok) window.researchResponse = await r.clone().json(); return r; };
  ` })
  await send('Page.navigate', { url: 'http://127.0.0.1:5173/' })
  for (let i = 0; i < 100 && !await evaluate('!!document.querySelector(".dropzone")'); i++) await wait(100)
  for (const bytes of documents) {
    await evaluate(`window.researchResponse = null; (() => { const bytes = Uint8Array.from(atob(${JSON.stringify(bytes)}), c => c.charCodeAt(0)); const d = new DataTransfer(); d.items.add(new File([bytes], 'fictional.docx', {type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'})); document.querySelector('.dropzone').dispatchEvent(new DragEvent('drop', {bubbles:true, dataTransfer:d})); })()`)
    for (let i = 0; i < 100 && !await evaluate('!!document.querySelector(".analyze-row button")'); i++) await wait(100)
    await evaluate(`document.querySelector('.analyze-row button').click()`)
    for (let i = 0; i < 150 && !await evaluate('!!window.researchResponse && !!document.querySelector(".authorship-status-value")'); i++) await wait(100)
    const result = await evaluate(`({text:document.querySelector('.authorship-panel')?.innerText, score:window.researchResponse?.model_diagnostic.ai_class_probability})`)
    assert.equal(typeof result.score, 'number', JSON.stringify(result))
    assert.ok(result.text.includes((result.score * 100).toFixed(1) + '%'), JSON.stringify(result))
    for (const width of [1440, 768, 390, 320]) {
      await send('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: false })
      assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'), true, `overflow at ${width}px`)
    }
  }
  console.log('Two fictional CVs: displayed scores match real backend output; responsive widths passed.')
} finally {
  socket?.close()
  browser.kill()
  await new Promise(resolve => { if (browser.exitCode !== null) resolve(); else browser.once('exit', resolve) })
  await rm(profile, { recursive: true, force: true })
}

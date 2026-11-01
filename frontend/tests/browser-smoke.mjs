// Optional: Node 22+ and Chrome. Start Vite first, then run node tests/browser-smoke.mjs.
import { spawn } from 'node:child_process'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import assert from 'node:assert/strict'

const chrome = process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const profile = await mkdtemp(join(tmpdir(), 'cvdetect-browser-'))
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
  socket = new WebSocket(targets.find(target => target.type === 'page').webSocketDebuggerUrl)
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject })
  let id = 0
  const pending = new Map()
  socket.onmessage = event => {
    const message = JSON.parse(event.data)
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id)
      pending.delete(message.id)
      message.error ? reject(Error(message.error.message)) : resolve(message.result)
    }
  }
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const requestId = ++id
    pending.set(requestId, { resolve, reject })
    socket.send(JSON.stringify({ id: requestId, method, params }))
  })
  const evaluate = async expression => {
    const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
    if (result.exceptionDetails) throw Error(result.exceptionDetails.text)
    return result.result.value
  }
  await send('Page.enable')
  // Deterministic mock API: the browser still exercises real React upload and drag events.
  await send('Page.addScriptToEvaluateOnNewDocument', { source: `
    window.requestedUrls = [];
    window.fetch = async (url, options) => {
      window.requestedUrls.push(String(url));
      if (String(url).endsWith('/api/health')) return new Response(JSON.stringify({status:'ok'}));
      if (window.failRequest) throw new Error('offline');
      if (String(url).endsWith('/api/cv/extract')) return new Response(JSON.stringify({filename:'fictional.pdf',file_type:'pdf',character_count:17,extracted_text:'Fictional preview'}));
      if (window.failAnalysis) return new Response(JSON.stringify({detail:'Unable to analyze this CV.'}), {status:503});
      return new Response(JSON.stringify({overall_score:75,categories:{structure:{score:80,explanation:'Structure explanation'},experience:{score:70,explanation:'Experience explanation'},skills:{score:75,explanation:'Skills explanation'},readability:{score:75,explanation:'Readability explanation'}},strengths:['Clear structure'],weaknesses:['Review details'],recommendations:['Add context'],method:'Rules have limitations.',writing_insights:window.emptyInsights ? [] : [{id:'test',type:'generic_phrase',priority:'low',explanation:'Consider wording.',recommendation:'Add context.'}]}));
    };` })
  await send('Page.navigate', { url: 'http://127.0.0.1:5173/' })
  for (let i = 0; i < 100 && !await evaluate('!!document.querySelector(".dropzone")'); i++) await wait(100)
  assert.equal(await evaluate('!!document.querySelector(".dropzone")'), true)
  // Exercise the actual drop handler, including validation and extraction preview.
  const drop = name => evaluate(`(() => { const d = new DataTransfer(); d.items.add(new File(['fictional'], ${JSON.stringify(name)}, {type:'application/pdf'})); document.querySelector('.dropzone').dispatchEvent(new DragEvent('drop', {bubbles:true, dataTransfer:d})); })()`)
  await drop('fictional.pdf')
  await wait(150)
  assert.match(await evaluate('document.body.innerText'), /fictional.pdf[\s\S]*Fictional preview/)
  if (process.env.EXPECT_PUBLIC_ONLY === '1') assert.equal(await evaluate('!!document.querySelector(".local-research")'), false)
  await evaluate(`[...document.querySelectorAll('button')].find(b => b.textContent.includes('Analyze CV')).click()`)
  await wait(150)
  const panel = await evaluate(`document.querySelector('.authorship-panel').innerText`)
  assert.match(panel, /INCONCLUSIVE/)
  assert.match(panel, /NOT YET VALIDATED/)
  assert.match(panel, /no AI-authorship model was run by the public analysis/i)
  assert.match(panel, /placeholder, not a model inference/i)
  assert.doesNotMatch(panel, /\d+\s*%|likely\s+(AI|human)|AI[- ]generated\s*:\s*\d/i)
  assert.match(await evaluate('document.body.innerText'), /Writing observations[\s\S]*Consider wording/)
  assert.equal(await evaluate(`(() => { const a = document.querySelector('.authorship-panel'); const w = document.querySelector('.writing-section'); const q = document.querySelector('.quality-details'); return !!(a.compareDocumentPosition(w) & Node.DOCUMENT_POSITION_FOLLOWING) && !!(w.compareDocumentPosition(q) & Node.DOCUMENT_POSITION_FOLLOWING); })()`), true)
  assert.equal(await evaluate(`document.querySelector('.quality-details').open`), false)
  await evaluate(`document.querySelector('.quality-details > summary').focus()`)
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
  await send('Input.dispatchKeyEvent', { type: 'char', text: '\r', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
  assert.equal(await evaluate(`document.querySelector('.quality-details').open`), true)
  assert.match(await evaluate(`document.querySelector('.quality-details').innerText`), /Overall quality score[\s\S]*75[\s\S]*Structure[\s\S]*80[\s\S]*Recommendations/)
  await evaluate(`document.querySelector('.category-card details > summary').click()`)
  assert.match(await evaluate(`document.querySelector('.category-card details').innerText`), /Structure explanation/)
  assert.equal(await evaluate(`window.requestedUrls.some(u => /research|experimental|\.pkl|\.joblib/i.test(u))`), false)
  for (const width of [1440, 1024, 768, 390, 320]) {
    await send('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: false })
    const overflow = await evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth')
    if (overflow) console.log(await evaluate(`JSON.stringify({innerWidth, client:document.documentElement.clientWidth, scroll:document.documentElement.scrollWidth, elements:[...document.querySelectorAll('*')].filter(e => e.getBoundingClientRect().right > document.documentElement.clientWidth + 1).map(e => [e.tagName, e.className, e.getBoundingClientRect().right]).slice(0, 10)})`))
    assert.equal(overflow, false, `horizontal overflow at ${width}px`)
    console.log(`${width}px: no horizontal overflow`)
  }
  await evaluate('window.emptyInsights = true')
  await evaluate(`[...document.querySelectorAll('button')].find(b => b.textContent.includes('Analyze CV')).click()`)
  await wait(100)
  assert.match(await evaluate('document.body.innerText'), /No wording suggestions were found/)
  await evaluate('window.failAnalysis = true')
  await evaluate(`[...document.querySelectorAll('button')].find(b => b.textContent.includes('Analyze CV')).click()`)
  await wait(100)
  assert.match(await evaluate('document.body.innerText'), /Unable to analyze this CV/)
  assert.equal(await evaluate(`!!document.querySelector('.authorship-panel')`), false)
  await evaluate('window.failAnalysis = false')
  await drop('invalid.txt')
  await wait(100)
  assert.match(await evaluate('document.body.innerText'), /Choose a PDF or DOCX file/)
  await evaluate(`(() => { const d = new DataTransfer(); d.items.add(new File([new Uint8Array(5 * 1024 * 1024 + 1)], 'large.pdf')); document.querySelector('.dropzone').dispatchEvent(new DragEvent('drop', {bubbles:true, dataTransfer:d})); })()`)
  await wait(100)
  assert.match(await evaluate('document.body.innerText'), /File must be 5 MB or smaller/)
  await evaluate(`(() => { const d = new DataTransfer(); d.items.add(new File(['a'], 'one.pdf')); d.items.add(new File(['b'], 'two.pdf')); document.querySelector('.dropzone').dispatchEvent(new DragEvent('drop', {bubbles:true, dataTransfer:d})); })()`)
  await wait(100)
  assert.match(await evaluate('document.body.innerText'), /Choose exactly one file/)
  await evaluate('window.failRequest = true')
  await drop('fictional.pdf')
  await wait(100)
  assert.match(await evaluate('document.body.innerText'), /Could not connect to the backend/)
  console.log('AI-first unavailable status, keyboard quality section, upload, preview, observations, empty state and errors: passed (mock API)')
} finally {
  socket?.close()
  browser.kill()
  await new Promise(resolve => { if (browser.exitCode !== null) resolve(); else browser.once('exit', resolve) })
  await rm(profile, { recursive: true, force: true })
}

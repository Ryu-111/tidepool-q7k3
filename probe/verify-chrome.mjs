// Only inspects our nonce-addressed dummy page and clicks its verifier. Never fills any field.
const [port, expectedUrl, phase] = process.argv.slice(2);
if (!/^\d+$/.test(port)
    || !/^http:\/\/localhost:8765\/(patterns\/[a-z]+\.html)?\?run=[0-9a-f]{32}$/.test(expectedUrl)) {
  throw new Error('Invalid probe target');
}
const tabs = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const tab = tabs.find(t => t.type === 'page' && t.url === expectedUrl);
if (!tab) throw new Error('Unique probe tab not found');
const expression = `(() => {
  if (location.href !== ${JSON.stringify(expectedUrl)}) return false;
  const f = document.querySelector('#fixture');
  if (!f) return false;
  if (typeof window.probeReady === 'function') {  // pattern pages carry their own expectations
    if (${JSON.stringify(phase)} === 'ready') return window.probeReady();
    document.querySelector('#verify').click();
    const text = document.querySelector('#result').textContent;
    return text.startsWith('PASS:') || text;  // FAIL text names only the mismatched fields
  }
  if (f.elements.hidden.getClientRects().length !== 0) return false;
  if (${JSON.stringify(phase)} === 'ready') {
    return ['family-name','given-name','postal-code','address-line1','password']
      .every(k => f.elements[k].value === '')
      && f.elements.email.value === 'do-not-overwrite@example.invalid'
      && f.elements.hidden.value === '';
  }
  document.querySelector('#verify').click();
  return document.querySelector('#result').textContent ===
    'PASS: 5項目一括入力・既存値保持・非表示欄未入力';
})()`;
await new Promise((resolve, reject) => {
  const socket = new WebSocket(tab.webSocketDebuggerUrl);
  const timer = setTimeout(() => { socket.close(); reject(new Error('Probe verification timeout')); }, 8000);
  socket.addEventListener('open', () => socket.send(JSON.stringify({
    id: 1, method: 'Runtime.evaluate', params: { expression, returnByValue: true }
  })));
  socket.addEventListener('error', () => {
    clearTimeout(timer); socket.close(); reject(new Error('Probe debugging connection failed'));
  });
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.id !== 1) return;
    clearTimeout(timer); socket.close();
    if (message.result?.result?.value === true) resolve();
    else {
      const detail = message.result?.result?.value;
      reject(new Error('Probe page assertion failed'
        + (typeof detail === 'string' && /^FAIL: [a-z0-9_, ]*$/.test(detail) ? ` (${detail})` : '')));
    }
  });
});
const pattern = new URL(expectedUrl).pathname !== '/';
console.log(pattern
  ? (phase === 'ready' ? 'PASS: fresh pattern page, all expected fields empty'
                       : 'PASS: every expected pattern field has its exact value')
  : (phase === 'ready' ? 'PASS: fresh dummy page, hidden field is invisible'
                       : 'PASS: verified five fields and unchanged existing/hidden values'));

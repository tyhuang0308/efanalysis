// 執行功能測驗分析：頁面互動。計分邏輯在 analysis.py。
{
const PYO = 'https://cdn.jsdelivr.net/pyodide/v0.29.5/full/';
const MAXFILES = 20;
const VALID = /^[A-Za-z]+\d+[FNDW]\.txt$/i;
const TEST = {F:'Flanker', N:'N-back', D:'DCCS', W:'WCST'};
const $ = id => document.getElementById(id);
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

let py = null, ready = false, busy = false;
const kept = new Map();      // path -> File
const skipped = new Map();   // path -> reason
const outputs = new Map();   // xlsx name -> Uint8Array
let zipBytes = null;
let fresh = new Set();       // paths added by the latest drop or pick, highlighted briefly
let freshT = 0;
let opSkips = 0;             // files skipped during the current drop or pick

function setEngine(s, text){ $('engine').dataset.s = s; $('engineText').textContent = text; refresh(); }
let toastT = 0;
function toast(text, isErr){ const t = $('toast'); t.textContent = text; t.classList.toggle('err', !!isErr); t.classList.add('on'); clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove('on'), 4200); }
function say(text, isErr){ $('msg').textContent = text || ''; $('msg').classList.toggle('err', !!isErr); }
const baseName = p => p.split('/').pop();

function addFile(path, file){
  const name = baseName(path);
  if (!name || name.startsWith('.')) return;
  if (!VALID.test(name)) { skipped.set(path, '檔名不符合格式'); opSkips++; return; }
  for (const p of kept.keys()) if (p !== path && baseName(p).toLowerCase() === name.toLowerCase()) { skipped.set(path, '和' + p + '檔名重複'); opSkips++; return; }
  kept.set(path, file);
}

const readEntries = r => new Promise((res, rej) => r.readEntries(res, rej));
const getFile = en => new Promise((res, rej) => en.file(res, rej));
async function walk(en){
  if (en.isFile) { addFile(en.fullPath.replace(/^\//, ''), await getFile(en)); }
  else if (en.isDirectory) {
    const r = en.createReader(); let batch;
    do { batch = await readEntries(r); for (const e of batch) await walk(e); } while (batch.length);
  }
}

function refresh(){
  const q = $('queue'); q.replaceChildren();
  const items = [...kept.keys()].sort((a, b) => baseName(a).localeCompare(baseName(b)));
  if (!items.length) q.append(el('li', 'empty', '還沒有檔案。把資料夾拖到上方的框裡，或按「選擇資料夾」'));
  for (const p of items) {
    const li = el('li', fresh.has(p) ? 'new' : ''); const name = baseName(p);
    li.append(el('span', 'chip', TEST[name.slice(-5, -4).toUpperCase()] || '?'));
    const info = el('span', 'nm', name); if (p !== name) info.append(el('span', 'pt', p));
    const rm = el('button', '', '移除'); rm.setAttribute('aria-label', '移除' + name);
    rm.onclick = () => { kept.delete(p); refresh(); };
    li.append(info, rm); q.append(li);
  }
  const n = kept.size, over = n > MAXFILES;
  $('count').textContent = n + ' / ' + MAXFILES; $('count').classList.toggle('over', over);
  $('run').disabled = !ready || busy || !n || over;
  $('run').textContent = busy ? $('run').textContent : (ready ? '完成，開始分析' : '分析引擎載入中…');
  $('clear').disabled = busy || (!n && !skipped.size);
  if (!busy) say(over ? '目前有' + n + '個符合格式的檔案，一次最多' + MAXFILES + '個，請移除一些或分批分析' : '', over);
  $('skipBox').hidden = !skipped.size;
  $('skipSum').textContent = '已略過' + skipped.size + '個檔案';
  $('skipList').replaceChildren(...[...skipped].map(([p, why]) => el('li', '', p + '（' + why + '）')));
}

// ---- Drop zone: clear feedback for every drop or pick ----
const tray = $('tray');
const IDLE = ['把一個或多個資料夾拖到這裡', '可以一次拖好幾個，也可以分好幾次拖'];
function setDrop(state, title, sub){
  tray.dataset.state = state;
  $('dropTitle').textContent = title; $('dropSub').textContent = sub;
}

// Run one add operation (drop or picker) and report what it changed.
async function ingest(work){
  const before = new Set(kept.keys()); opSkips = 0;
  setDrop('reading', '正在讀取…', '資料夾比較大時要等幾秒');
  await work();
  const added = [...kept.keys()].filter(p => !before.has(p));
  const newSkips = opSkips;
  fresh = new Set(added); clearTimeout(freshT); freshT = setTimeout(() => { fresh = new Set(); }, 3200);
  refresh();
  const total = kept.size;
  if (added.length) {
    setDrop('done', '已加入' + added.length + '個檔案', '清單裡共有' + total + '個檔案。可以繼續拖入，或到下方按「完成，開始分析」');
    toast('已加入' + added.length + '個檔案');
  } else if (newSkips) {
    setDrop('warn', '沒有找到符合格式的檔案', '請檢查檔名');
  } else if (before.size) {
    setDrop('warn', '這些檔案已經在清單裡了', '清單裡共有' + total + '個檔案');
  } else {
    setDrop('warn', '沒有讀到任何檔案', '請拖入資料夾或.txt檔，或改按下方的按鈕選擇');
  }
}

// Keep stray drops from replacing the page
['dragover', 'drop'].forEach(t => window.addEventListener(t, e => e.preventDefault()));
let saved = null;
tray.addEventListener('dragenter', e => {
  e.preventDefault();
  if (tray.dataset.state === 'over') return;
  saved = [tray.dataset.state, $('dropTitle').textContent, $('dropSub').textContent];
  setDrop('over', '放開滑鼠，加入這些檔案', '資料夾裡符合格式的.txt會自動挑出來');
});
tray.addEventListener('dragover', e => e.preventDefault());
tray.addEventListener('dragleave', e => {
  if (tray.contains(e.relatedTarget)) return;
  if (tray.dataset.state === 'over' && saved) setDrop(...saved);
});
tray.addEventListener('drop', async e => {
  e.preventDefault();
  const items = [...e.dataTransfer.items];
  const entries = items.map(i => i.webkitGetAsEntry && i.webkitGetAsEntry()).filter(Boolean);
  const files = [...e.dataTransfer.files];
  await ingest(async () => {
    if (entries.length) { for (const en of entries) await walk(en); }
    else for (const f of files) addFile(f.name, f);
  });
});
for (const id of ['pickDir', 'pickFiles']) $(id).addEventListener('change', async e => {
  const files = [...e.target.files]; e.target.value = '';
  if (!files.length) return;
  await ingest(async () => { for (const f of files) addFile(f.webkitRelativePath || f.name, f); });
});
$('clear').onclick = () => { kept.clear(); skipped.clear(); fresh = new Set(); setDrop('idle', ...IDLE); refresh(); };


// Files loaded next to this page. Keep their names in sync with the repository.
const WHEELS = ['wheels/et_xmlfile-2.0.0-py3-none-any.whl', 'wheels/openpyxl-3.1.5-py2.py3-none-any.whl'];
const PY_FILES = ['analysis.py', 'runner.py'];

async function fetchOk(url, kind){
  const r = await fetch(url, { cache: 'no-cache' });
  if (!r.ok) throw new Error('讀不到' + url + '（HTTP ' + r.status + '），請確認這個檔案有上傳到GitHub');
  return kind === 'text' ? r.text() : new Uint8Array(await r.arrayBuffer());
}

async function boot(){
  try {
    if (location.protocol === 'file:') throw new Error('這個版本要用網址打開（例如GitHub Pages），不能直接雙擊index.html');
    if (typeof loadPyodide !== 'function') throw new Error('無法連到Pyodide伺服器，請確認網路連線');
    py = await loadPyodide({ indexURL: PYO });
    setEngine('load', '正在載入pandas…');
    await py.loadPackage(['numpy', 'pandas'], { messageCallback: () => {} });
    for (const url of WHEELS) py.FS.writeFile('/tmp/' + url.split('/').pop(), await fetchOk(url));
    py.globals.set('WHEEL_FILES', py.toPy(WHEELS.map(u => '/tmp/' + u.split('/').pop())));
    py.runPython("import zipfile, site, importlib\nsp = site.getsitepackages()[0]\nfor w in WHEEL_FILES:\n    zipfile.ZipFile(w).extractall(sp)\nimportlib.invalidate_caches()\nimport openpyxl");
    setEngine('load', '正在載入計分程式…');
    for (const f of PY_FILES) py.runPython(await fetchOk(f, 'text'), { filename: f });
    ready = true; setEngine('ok', '分析引擎已就緒');
  } catch (err) {
    console.error(err);
    setEngine('err', '分析引擎載入失敗');
    say(String(err && err.message || err), true);
  }
}

const sleep = ms => new Promise(r => setTimeout(r, ms));
$('run').onclick = async () => {
  if (!ready || busy) return;
  busy = true; outputs.clear(); zipBytes = null; refresh();
  const items = [...kept.entries()].sort((a, b) => baseName(a[0]).localeCompare(baseName(b[0])));
  $('results').hidden = false; $('cards').replaceChildren(); $('zipBtn').hidden = true;
  let ok = 0, bad = 0;
  try {
    py.runPython("import shutil; shutil.rmtree('/work/in', ignore_errors=True); reset_outputs()");
    const runOne = py.globals.get('run_one');
    for (let i = 0; i < items.length; i++) {
      const [path, file] = items[i];
      $('run').textContent = '分析中' + (i + 1) + ' / ' + items.length;
      $('sum').textContent = '正在分析' + baseName(path) + '…';
      await sleep(20);
      const full = '/work/in/' + path;
      py.FS.mkdirTree(full.slice(0, full.lastIndexOf('/')));
      py.FS.writeFile(full, new Uint8Array(await file.arrayBuffer()));
      const rec = JSON.parse(runOne(full));
      if (rec.ok) { ok++; outputs.set(rec.out, py.FS.readFile(rec.out_path)); } else bad++;
      $('cards').append(card(rec, path));
    }
    runOne.destroy();
    const z = py.runPython('make_zip()');
    if (z) { zipBytes = py.FS.readFile(z); $('zipBtn').hidden = false; }
    $('sum').textContent = ok ? ok + '個成功！' + (bad ? bad + '個失敗，請看下方的錯誤訊息' : '')
                              : '沒有成功產生任何Excel檔，請看下方錯誤訊息';
  } catch (err) {
    console.error(err); say('分析時發生錯誤：' + (err && err.message || err), true);
  } finally {
    busy = false; refresh();
    $('results').scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
  }
};

function card(rec, path){
  const c = el('article', 'card' + (rec.ok ? '' : ' fail'));
  if (rec.ok) { const box = el('div', 'tbl'); box.innerHTML = rec.preview; c.append(box); } // pandas escapes cell values
  else {
    const box = el('div', 'tbl errbox'); box.append(el('p', 'errtxt', rec.error));
    const d = el('details'); d.append(el('summary', '', '詳細錯誤訊息'), el('pre', '', rec.trace || '')); box.append(d); c.append(box);
  }
  const cap = el('div', 'cap'); const left = el('div');
  left.append(el('span', 'nm', rec.file), el('span', 'st', rec.ok ? '完成' : '失敗'));
  cap.append(left, el('span', 'code', rec.test)); c.append(cap);
  if (rec.ok) { const btn = el('button', 'rect', '下載' + rec.out); btn.onclick = () => saveFile(rec.out, outputs.get(rec.out)); c.append(btn); }
  return c;
}

$('zipBtn').onclick = () => zipBytes && saveFile('outputs.zip', zipBytes);

async function saveFile(name, bytes){
  const type = name.endsWith('.zip') ? 'application/zip' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
  const blob = new Blob([bytes], { type });
  const host = (window.claude && typeof window.claude.use === 'function') ? await window.claude.use('downloads') : undefined;
  if (host === undefined) {  // opened as a normal web page
    const a = el('a'); a.href = URL.createObjectURL(blob); a.download = name;
    document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 4000); return;
  }
  if (host === null) { toast('這個畫面不能下載檔案，請在電腦的瀏覽器中開啟這個頁面', true); return; }
  try { await host.save({ filename: name, data: blob }); toast('已下載' + name); }
  catch (e) {
    const code = e && e.code;
    if (code === 'declined') return;
    if (code === 'rate_limited') toast('下載確認視窗已經開著，請先處理它再試一次', true);
    else if (code === 'host_unavailable') toast('這個App不能存檔，請改用電腦的瀏覽器開啟這個頁面', true);
    else toast('下載失敗：' + (e && e.message || code), true);
  }
}

refresh();
boot();
}

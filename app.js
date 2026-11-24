// EF 測驗批次分析：頁面互動。計分邏輯在 analysis.py。
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

function setEngine(s, text){ $('engine').dataset.s = s; $('engineText').textContent = text; refresh(); }
let toastT = 0;
function toast(text, isErr){ const t = $('toast'); t.textContent = text; t.classList.toggle('err', !!isErr); t.classList.add('on'); clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove('on'), 4200); }
function say(text, isErr){ $('msg').textContent = text || ''; $('msg').classList.toggle('err', !!isErr); }
const baseName = p => p.split('/').pop();

function addFile(path, file){
  const name = baseName(path);
  if (!name || name.startsWith('.')) return;
  if (!VALID.test(name)) { skipped.set(path, '檔名不符合格式'); return; }
  for (const p of kept.keys()) if (p !== path && baseName(p).toLowerCase() === name.toLowerCase()) { skipped.set(path, '和 ' + p + ' 檔名重複'); return; }
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
  if (!items.length) q.append(el('li', 'empty', '還沒有檔案。把資料夾拖到左邊，或按「選擇資料夾」。'));
  for (const p of items) {
    const li = el('li'); const name = baseName(p);
    li.append(el('span', 'chip', TEST[name.slice(-5, -4).toUpperCase()] || '?'));
    const info = el('span', 'nm', name); if (p !== name) info.append(el('span', 'pt', p));
    const rm = el('button', '', '移除'); rm.setAttribute('aria-label', '移除 ' + name);
    rm.onclick = () => { kept.delete(p); refresh(); };
    li.append(info, rm); q.append(li);
  }
  const n = kept.size, over = n > MAXFILES;
  $('count').textContent = n + ' / ' + MAXFILES; $('count').classList.toggle('over', over);
  $('run').disabled = !ready || busy || !n || over;
  $('run').textContent = busy ? $('run').textContent : (ready ? '完成，開始分析' : '分析引擎載入中…');
  $('clear').disabled = busy || (!n && !skipped.size);
  if (!busy) say(over ? '目前有 ' + n + ' 個符合格式的檔案，一次最多 ' + MAXFILES + ' 個，請移除一些或分批分析。' : '', over);
  $('skipBox').hidden = !skipped.size;
  $('skipSum').textContent = '已略過 ' + skipped.size + ' 個檔案';
  $('skipList').replaceChildren(...[...skipped].map(([p, why]) => el('li', '', p + '（' + why + '）')));
}

// Keep stray drops from replacing the page
['dragover', 'drop'].forEach(t => window.addEventListener(t, e => e.preventDefault()));
const tray = $('tray');
tray.addEventListener('dragover', e => { e.preventDefault(); tray.classList.add('over'); });
tray.addEventListener('dragleave', () => tray.classList.remove('over'));
tray.addEventListener('drop', async e => {
  e.preventDefault(); tray.classList.remove('over');
  const entries = [...e.dataTransfer.items].map(i => i.webkitGetAsEntry && i.webkitGetAsEntry()).filter(Boolean);
  say('讀取資料夾中…');
  if (entries.length) { for (const en of entries) await walk(en); }
  else for (const f of e.dataTransfer.files) addFile(f.name, f);
  refresh();
});
for (const id of ['pickDir', 'pickFiles']) $(id).addEventListener('change', e => {
  for (const f of e.target.files) addFile(f.webkitRelativePath || f.name, f);
  e.target.value = ''; refresh();
});
$('clear').onclick = () => { kept.clear(); skipped.clear(); refresh(); };


// Files loaded next to this page. Keep their names in sync with the repository.
const WHEELS = ['wheels/et_xmlfile-2.0.0-py3-none-any.whl', 'wheels/openpyxl-3.1.5-py2.py3-none-any.whl'];
const PY_FILES = ['analysis.py', 'runner.py'];

async function fetchOk(url, kind){
  const r = await fetch(url, { cache: 'no-cache' });
  if (!r.ok) throw new Error('讀不到 ' + url + '（HTTP ' + r.status + '），請確認這個檔案有上傳到 GitHub');
  return kind === 'text' ? r.text() : new Uint8Array(await r.arrayBuffer());
}

async function boot(){
  try {
    if (location.protocol === 'file:') throw new Error('這個版本要用網址打開（例如 GitHub Pages），不能直接雙擊 index.html');
    if (typeof loadPyodide !== 'function') throw new Error('無法連到 Pyodide 伺服器，請確認網路連線');
    py = await loadPyodide({ indexURL: PYO });
    setEngine('load', '正在載入 pandas…');
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
      $('run').textContent = '分析中 ' + (i + 1) + ' / ' + items.length;
      $('sum').textContent = '正在分析 ' + baseName(path) + '…';
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
    $('sum').textContent = ok ? ok + ' 個成功' + (bad ? '、' + bad + ' 個失敗' : '') + '。每個 Excel 都有 results 和 analysis 工作表，WCST 另有 learning to learn index。'
                              : '沒有成功產生任何 Excel 檔，請看下方錯誤訊息。';
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
  if (rec.ok) { const btn = el('button', 'rect', '下載 ' + rec.out); btn.onclick = () => saveFile(rec.out, outputs.get(rec.out)); c.append(btn); }
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
  if (host === null) { toast('這個畫面不能下載檔案，請在電腦的瀏覽器中開啟這個頁面。', true); return; }
  try { await host.save({ filename: name, data: blob }); toast('已下載 ' + name); }
  catch (e) {
    const code = e && e.code;
    if (code === 'declined') return;
    if (code === 'rate_limited') toast('下載確認視窗已經開著，請先處理它再試一次。', true);
    else if (code === 'host_unavailable') toast('這個 App 不能存檔，請改用電腦的瀏覽器開啟這個頁面。', true);
    else toast('下載失敗：' + (e && e.message || code), true);
  }
}

refresh();
boot();
}

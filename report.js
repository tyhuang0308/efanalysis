// 產生報告書：Google登入、讀取試算表與範本、呼叫report.py
{
const C = window.EF_CONFIG || {};
const A = window.EFApp;
const SCOPE = 'https://www.googleapis.com/auth/drive.readonly';
const DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
const WHEELS = ['wheels/docx_mailmerge-0.5.0-py2.py3-none-any.whl', 'wheels/python_docx-1.2.0-py3-none-any.whl'];
const FONT = 'fonts/NotoSansTC-report.otf';
const $ = id => document.getElementById(id);
const el = A.el;
const fileName = u => u.split('/').pop();

let token = null, tokenExp = 0, tokenClient = null, pending = null;
let sheetIds = null;        // ids found in the report sheet (null until signed in)
let engine = null;          // promise of the report.py namespace
let busy = false;
const outputs = new Map();  // docx name -> bytes
let zipBytes = null;

function msg(text, isErr){ const m = $('rpMsg'); m.textContent = text || ''; m.classList.toggle('err', !!isErr); }
function auth(text){ $('rpAuth').textContent = text || ''; }

// ---------- Google sign-in (Google Identity Services, token model) ----------
function ensureClient(){
  if (tokenClient) return true;
  if (!C.googleClientId) throw new Error('尚未設定Google登入：請在config.js填入googleClientId');
  if (!(window.google && google.accounts && google.accounts.oauth2)) throw new Error('Google登入元件還沒載入，請確認網路連線後再試一次');
  tokenClient = google.accounts.oauth2.initTokenClient({
    client_id: C.googleClientId,
    scope: SCOPE,
    callback: resp => {
      const p = pending; pending = null; if (!p) return;
      if (resp.error) return p.rej(new Error('Google登入失敗：' + (resp.error_description || resp.error)));
      if (!google.accounts.oauth2.hasGrantedAllScopes(resp, SCOPE)) return p.rej(new Error('需要同意讀取Google雲端硬碟檔案的權限，才能讀取試算表和範本'));
      token = resp.access_token;
      tokenExp = Date.now() + (Number(resp.expires_in) || 3600) * 1000;
      p.res(token);
    },
    error_callback: err => {
      const p = pending; pending = null; if (!p) return;
      p.rej(new Error(err && err.type === 'popup_closed' ? '登入視窗被關閉了' : '無法開啟Google登入視窗，請允許這個網站的彈出式視窗'));
    },
  });
  return true;
}

// Call this first thing inside a click handler, so the browser allows the popup
function getToken(){
  if (token && Date.now() < tokenExp - 60000) return Promise.resolve(token);
  try { ensureClient(); } catch (e) { return Promise.reject(e); }
  return new Promise((res, rej) => { pending = { res, rej }; tokenClient.requestAccessToken({ prompt: '' }); });
}

async function gfetch(url, kind, what){
  const r = await fetch(url, { headers: { Authorization: 'Bearer ' + token } });
  if (r.status === 401) { token = null; throw new Error('Google登入已過期，請再按一次'); }
  if (!r.ok) {
    let reason = '';
    try { const j = await r.json(); reason = (j.error && j.error.message) || ''; } catch (e) { /* not JSON */ }
    const apiOff = /has not been used|is disabled|SERVICE_DISABLED/i.test(reason);
    const api = url.includes('sheets.googleapis.com') ? 'Google Sheets API' : 'Google Drive API';
    const err = new Error(apiOff
      ? what + '：Google Cloud專案還沒啟用' + api + '，請到Google Cloud啟用後等幾分鐘再試（' + reason + '）'
      : r.status === 403 || r.status === 404
      ? what + '：請確認這個檔案已分享給你登入的Google帳號' + (reason ? '（' + reason + '）' : '')
      : what + '（HTTP ' + r.status + '）' + (reason ? '：' + reason : ''));
    err.status = r.status; err.reason = reason; throw err;
  }
  return kind === 'json' ? r.json() : new Uint8Array(await r.arrayBuffer());
}

async function readSheet(){
  const range = "'" + String(C.sheetName).replace(/'/g, "''") + "'";
  const url = 'https://sheets.googleapis.com/v4/spreadsheets/' + encodeURIComponent(C.sheetId) +
              '/values/' + encodeURIComponent(range) + '?valueRenderOption=FORMATTED_VALUE';
  const j = await gfetch(url, 'json', '讀不到試算表');
  const values = j.values || [];
  const k = (values[0] || []).indexOf('id');
  if (k < 0) throw new Error(C.sheetName + '工作表的第一列找不到「id」欄位');
  sheetIds = new Set(values.slice(1).map(r => r[k] || '').filter(v => v !== ''));
  auth('已登入，試算表共有' + sheetIds.size + '位個案');
  check();
  return values;
}

async function readTemplate(){
  const base = 'https://www.googleapis.com/drive/v3/files/' + encodeURIComponent(C.templateId);
  try { return await gfetch(base + '?alt=media&supportsAllDrives=true', 'bytes', '讀不到報告書範本'); }
  catch (e) {
    // A native Google Docs file cannot be downloaded directly; export it as .docx instead
    if (e.status === 403 && /export/i.test(e.reason)) return gfetch(base + '/export?mimeType=' + encodeURIComponent(DOCX), 'bytes', '讀不到報告書範本');
    throw e;
  }
}

// ---------- Report engine (loaded the first time it is needed) ----------
async function fetchOk(url, text){
  const r = await fetch(url, { cache: 'no-cache' });
  if (!r.ok) throw new Error('讀不到' + url + '（HTTP ' + r.status + '），請確認這個檔案有上傳到GitHub');
  return text ? r.text() : new Uint8Array(await r.arrayBuffer());
}

function ensureEngine(stage){
  if (engine) return engine;
  engine = (async () => {
    stage('正在等待分析引擎…');
    const py = await A.pyReady;
    stage('正在載入報告書元件，第一次大約要10–20秒…');
    await py.loadPackage(['lxml', 'matplotlib', 'typing-extensions'], { messageCallback: () => {} });
    for (const url of WHEELS) py.FS.writeFile('/tmp/' + fileName(url), await fetchOk(url));
    py.globals.set('REPORT_WHEELS', py.toPy(WHEELS.map(u => '/tmp/' + fileName(u))));
    py.runPython("import zipfile, site, importlib\nsp = site.getsitepackages()[0]\nfor w in REPORT_WHEELS:\n    zipfile.ZipFile(w).extractall(sp)\nimportlib.invalidate_caches()");
    py.FS.mkdirTree('/work/report');
    py.FS.writeFile('/work/report/' + fileName(FONT), await fetchOk(FONT));
    const ns = py.globals.get('dict')();          // keep report.py apart from the analysis code
    py.runPython(await fetchOk('report.py', true), { globals: ns, filename: 'report.py' });
    return { py, ns };
  })();
  engine.catch(() => { engine = null; });
  return engine;
}

// ---------- UI ----------
function parseIds(text){ return [...new Set(text.split(/[\s,，、]+/).filter(Boolean))]; }

function check(){
  const want = parseIds($('rpIds').value);
  if (!sheetIds || !want.length) { $('rpCheck').textContent = ''; return; }
  const missing = want.filter(v => !sheetIds.has(v));
  $('rpCheck').textContent = missing.length ? '試算表裡找不到：' + missing.join('、') : '共' + want.length + '個ID，都在試算表裡';
  $('rpCheck').classList.toggle('err', missing.length > 0);
}
$('rpIds').addEventListener('input', check);

function setBusy(on){
  busy = on;
  $('rpRun').disabled = on; $('rpLogin').disabled = on;
  if (!on) $('rpRun').textContent = '產生報告書';
}

$('rpLogin').onclick = async () => {
  if (busy) return;
  const tk = getToken();            // first, so the popup is allowed
  setBusy(true); msg('');
  try {
    await tk; auth('已登入，正在讀取試算表…');
    await readSheet();
    $('rpLogin').hidden = true; $('rpLogout').hidden = false;
    ensureEngine(() => {}).catch(() => {});   // warm up the report engine in the background
  } catch (e) { auth(''); msg(e.message, true); }
  finally { setBusy(false); }
};

$('rpLogout').onclick = () => {
  if (token && window.google && google.accounts) google.accounts.oauth2.revoke(token, () => {});
  token = null; sheetIds = null;
  auth('已登出'); $('rpCheck').textContent = '';
  $('rpLogin').hidden = false; $('rpLogout').hidden = true;
};

function row(rec){
  const li = el('li', rec.ok ? '' : 'fail');
  li.append(el('span', 'nm', rec.id));
  const mid = el('span', 'st', rec.ok ? '完成' : rec.error);
  li.append(mid);
  if (rec.ok) {
    const b = el('button', 'rect', '下載' + rec.out);
    b.onclick = () => A.saveFile(rec.out, outputs.get(rec.out));
    li.append(b);
  } else if (rec.trace) {
    const d = el('details', 'why'); d.append(el('summary', '', '詳細錯誤訊息'), el('pre', '', rec.trace));
    li.append(d);
  } else li.append(el('span'));
  return li;
}

$('rpRun').onclick = async () => {
  if (busy) return;
  const want = parseIds($('rpIds').value);
  if (!want.length) { msg('請先輸入個案ID', true); $('rpIds').focus(); return; }
  const tk = getToken();            // first, so the popup is allowed
  setBusy(true); msg(''); outputs.clear(); zipBytes = null;
  $('rpZip').hidden = true; $('rpList').replaceChildren();
  const stage = t => { msg(t); };
  try {
    await tk;
    stage('正在讀取試算表…');
    const values = await readSheet();
    $('rpLogin').hidden = true; $('rpLogout').hidden = false;
    stage('正在讀取報告書範本…');
    const tpl = await readTemplate();
    const { py, ns } = await ensureEngine(stage);
    ns.get('load_sheet')(JSON.stringify(values));
    py.FS.writeFile('/work/report/template.docx', tpl);
    ns.get('reset_reports')();
    const makeOne = ns.get('make_one');
    let ok = 0, bad = 0;
    for (let i = 0; i < want.length; i++) {
      $('rpRun').textContent = '產生中' + (i + 1) + ' / ' + want.length;
      stage('正在產生' + want[i] + '的報告書…');
      await A.sleep(20);
      const rec = JSON.parse(makeOne(want[i]));
      if (rec.ok) { ok++; outputs.set(rec.out, py.FS.readFile(rec.out_path)); } else bad++;
      $('rpList').append(row(rec));
    }
    makeOne.destroy();
    const z = ns.get('zip_reports')();
    if (z) { zipBytes = py.FS.readFile(z); $('rpZip').hidden = false; }
    msg(ok ? ok + '份報告書已產生！' + (bad ? bad + '份失敗，請看下方的原因' : '') : '沒有產生任何報告書，請看下方的原因', !ok);
  } catch (e) {
    console.error(e); msg(e.message || String(e), true);
  } finally { setBusy(false); }
};

$('rpZip').onclick = () => zipBytes && A.saveFile('reports.zip', zipBytes);

if (!C.googleClientId) auth('尚未設定Google登入，請先在config.js填入用戶端ID');
}

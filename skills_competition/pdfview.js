// 模擬試題 PDF 檢視頁：用 PDF.js 顯示（手機、平板、電腦都能看；Android 的頁框不支援直接顯示 PDF）
// 每個版本有一個小頁面（例：115_v2.0_pdf.html），在 <body> 寫 data-pdf、data-html、data-title，共用這支程式。
// PDF.js 4.10.38（Apache-2.0）放在同一個資料夾：Worker 不能從其他網域（CDN）載入，否則會卡在「載入中」
import * as pdfjsLib from './pdfjs.min.js';
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL('./pdfjs.worker.min.js', import.meta.url).href;

const { pdf: pdfUrl, html: htmlUrl, title } = document.body.dataset;
const bar = document.getElementById('bar');
const pagesEl = document.getElementById('pages');

bar.innerHTML = `
  <span class="title">${title}</span>
  <span class="zoom">
    <button type="button" id="zOut" aria-label="縮小">－</button>
    <output id="zVal" aria-live="polite">100%</output>
    <button type="button" id="zIn" aria-label="放大">＋</button>
    <button type="button" id="zFit">符合寬度</button>
  </span>
  <a class="primary" href="${pdfUrl}" download>⬇ <span class="label">下載 PDF</span></a>
  <a href="${pdfUrl}" target="_blank" rel="noopener">🖨 <span class="label">列印／新分頁開啟</span></a>` +
  (htmlUrl ? `\n  <a href="${htmlUrl}">🌐 <span class="label">網頁版</span></a>` : '');   // 歷屆試題只有 PDF，沒有網頁版
// 正式試題 PDF 裡有未嵌入的英文標準字型（Times、Arial），需要 PDF.js 的標準字型資料；CMap 供中文字型對照備用
const PDFJS_DATA = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/';
const altLinks = () => `<a href="${pdfUrl}" download>直接下載 PDF</a>` + (htmlUrl ? ` 或改看 <a href="${htmlUrl}">網頁版</a>` : '');

let doc = null, fitScale = 1, zoom = 1;       // zoom：相對於「符合寬度」的倍率
const pageBoxes = [];                          // { el, canvas, page, rendered }

function fitWidthScale(page) {
  const avail = Math.min(pagesEl.clientWidth - 16, 1100);
  return avail / page.getViewport({ scale: 1 }).width;
}

function layout() {
  const s = fitScale * zoom;
  document.getElementById('zVal').textContent = Math.round(zoom * 100) + '%';
  for (const b of pageBoxes) {
    const vp = b.page.getViewport({ scale: s });
    b.el.style.width = vp.width + 'px';
    b.el.style.height = vp.height + 'px';
    b.rendered = false;
  }
  observeAll();
}

async function render(b) {
  if (b.rendered) return;
  b.rendered = true;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const vp = b.page.getViewport({ scale: fitScale * zoom * dpr });
  b.canvas.width = Math.floor(vp.width);
  b.canvas.height = Math.floor(vp.height);
  if (b.task) b.task.cancel();
  b.task = b.page.render({ canvasContext: b.canvas.getContext('2d'), viewport: vp });
  try { await b.task.promise; } catch (e) { if (e?.name !== 'RenderingCancelledException') b.rendered = false; }
}

let io = null;
function observeAll() {
  if (io) io.disconnect();
  io = new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) render(pageBoxes[+e.target.dataset.i]);
  }), { root: null, rootMargin: '600px 0px' });
  pageBoxes.forEach(b => io.observe(b.el));
}

function setZoom(z) { zoom = Math.max(0.5, Math.min(3, z)); layout(); }
document.getElementById('zIn').onclick = () => setZoom(zoom + 0.25);
document.getElementById('zOut').onclick = () => setZoom(zoom - 0.25);
document.getElementById('zFit').onclick = () => setZoom(1);
let rt = null;
addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { if (doc) { fitScale = fitWidthScale(pageBoxes[0].page); layout(); } }, 200); });

try {
  // PDF 約 3～4 MB，網路慢時要一段時間：顯示下載進度，8 秒後另外提示可直接下載或改看網頁版（仍繼續載入）
  const msg = document.getElementById('msg');
  const task = pdfjsLib.getDocument({
    url: pdfUrl,
    cMapUrl: PDFJS_DATA + 'cmaps/', cMapPacked: true,
    standardFontDataUrl: PDFJS_DATA + 'standard_fonts/',
  });
  let pct = '';
  const hintTimer = setTimeout(() => {
    msg.innerHTML = `載入中…<span id="pct">${pct}</span><br><small>檔案較大，網路較慢時請稍候；也可以 ${altLinks()}。</small>`;
  }, 8000);
  task.onProgress = ({ loaded, total }) => {
    if (!total) return;
    pct = ` ${Math.round(loaded / total * 100)}%（約 ${(total / 1048576).toFixed(1)} MB）`;
    const el = document.getElementById('pct');
    if (el) el.textContent = pct; else msg.firstChild.textContent = '載入中…' + pct;
  };
  doc = await task.promise;
  clearTimeout(hintTimer);
  msg.remove();
  for (let i = 1; i <= doc.numPages; i++) {
    const page = await doc.getPage(i);
    const el = document.createElement('div');
    el.className = 'page';
    el.dataset.i = i - 1;
    const canvas = document.createElement('canvas');
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', `第 ${i} 頁，共 ${doc.numPages} 頁`);
    const no = document.createElement('span');
    no.className = 'no';
    no.textContent = `${i} / ${doc.numPages}`;
    el.append(canvas, no);
    pagesEl.appendChild(el);
    pageBoxes.push({ el, canvas, page, rendered: false });
  }
  fitScale = fitWidthScale(pageBoxes[0].page);
  layout();
} catch (e) {
  pagesEl.innerHTML = `<div id="msg">PDF 載入失敗。請改用 <a href="${pdfUrl}" target="_blank" rel="noopener">直接開啟 PDF</a>` +
    (htmlUrl ? ` 或 <a href="${htmlUrl}">網頁版</a>` : '') + '。</div>';
}

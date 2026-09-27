// 模擬試題 PDF 檢視頁：用 PDF.js 顯示（手機、平板、電腦都能看；Android 的頁框不支援直接顯示 PDF）
// 每個版本有一個小頁面（例：115_v2.0_pdf.html），在 <body> 寫 data-pdf、data-html、data-title，共用這支程式。
import * as pdfjsLib from 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.10.38/pdf.min.mjs';
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.10.38/pdf.worker.min.mjs';

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
  <a href="${pdfUrl}" target="_blank" rel="noopener">🖨 <span class="label">列印／新分頁開啟</span></a>
  <a href="${htmlUrl}">🌐 <span class="label">網頁版</span></a>`;

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
  doc = await pdfjsLib.getDocument(pdfUrl).promise;
  document.getElementById('msg')?.remove();
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
  pagesEl.innerHTML = `<div id="msg">PDF 載入失敗。請改用 <a href="${pdfUrl}" target="_blank" rel="noopener">直接開啟 PDF</a> 或 <a href="${htmlUrl}">網頁版</a>。</div>`;
}

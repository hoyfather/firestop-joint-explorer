// PDF.js 기반 세부 인정내용 뷰어. pdf.min.mjs / pdf.worker.min.mjs 는 배포 시 같은 폴더에 생성됩니다.
let generation = 0;
let docTask = null;
let renderTask = null;
let resizeObserver = null;

window.startPdfViewer = async function (url) {
  const gen = ++generation;
  if (renderTask) { renderTask.cancel(); renderTask = null; }
  if (docTask) { docTask.destroy(); docTask = null; }
  if (resizeObserver) { resizeObserver.disconnect(); resizeObserver = null; }
  const viewer = document.querySelector('#pdfViewer');
  if (!viewer || !url) return;
  const message = viewer.querySelector('.pdf-message');
  const canvas = viewer.querySelector('canvas');
  const box = viewer.querySelector('.pdf-canvas');
  const label = viewer.querySelector('.pdf-page');
  const prev = viewer.querySelector('[data-pdf-previous]');
  const next = viewer.querySelector('[data-pdf-next]');
  const zin = viewer.querySelector('[data-pdf-zoom-in]');
  const zout = viewer.querySelector('[data-pdf-zoom-out]');
  const fit = viewer.querySelector('[data-pdf-fit]');
  const full = viewer.querySelector('[data-pdf-full]');
  let pageNumber = 1;
  let zoom = 1;
  const fail = () => { if (gen === generation) message.textContent = '문서를 표시하지 못했습니다. "PDF 저장" 또는 "연구원 출처 공고"에서 원문을 확인하세요.'; };
  try {
    const pdfjs = await import('./pdf.min.mjs');
    if (gen !== generation) return;
    pdfjs.GlobalWorkerOptions.workerSrc = new URL('./pdf.worker.min.mjs', import.meta.url).href;
    docTask = pdfjs.getDocument(url);
    const pdf = await docTask.promise;
    if (gen !== generation) return;
    async function draw() {
      if (renderTask) renderTask.cancel();
      message.textContent = '페이지를 그리는 중입니다.';
      const page = await pdf.getPage(pageNumber);
      if (gen !== generation) return;
      const base = page.getViewport({ scale: 1 });
      const avail = Math.max(240, box.clientWidth - 24);
      const viewport = page.getViewport({ scale: Math.min(2, avail / base.width) * zoom });
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(viewport.width * ratio);
      canvas.height = Math.floor(viewport.height * ratio);
      canvas.style.width = Math.floor(viewport.width) + 'px';
      canvas.style.height = Math.floor(viewport.height) + 'px';
      label.textContent = pageNumber + ' / ' + pdf.numPages;
      prev.disabled = pageNumber <= 1;
      next.disabled = pageNumber >= pdf.numPages;
      fit.disabled = zoom === 1;
      const task = page.render({ canvasContext: canvas.getContext('2d'), viewport, transform: ratio === 1 ? null : [ratio, 0, 0, ratio, 0, 0] });
      renderTask = task;
      try { await task.promise; if (gen === generation) message.textContent = ''; }
      catch (err) { if (err.name !== 'RenderingCancelledException') throw err; }
      finally { if (renderTask === task) renderTask = null; }
    }
    const update = () => draw().catch(fail);
    let lastWidth = box.clientWidth, timer;
    prev.onclick = () => { if (pageNumber > 1) { pageNumber--; update(); box.scrollTop = 0; } };
    next.onclick = () => { if (pageNumber < pdf.numPages) { pageNumber++; update(); box.scrollTop = 0; } };
    zin.onclick = () => { zoom = Math.min(3, zoom + 0.25); update(); };
    zout.onclick = () => { zoom = Math.max(0.5, zoom - 0.25); update(); };
    fit.onclick = () => { zoom = 1; update(); };
    if (full && document.fullscreenEnabled && viewer.requestFullscreen) {
      full.hidden = false;
      full.onclick = async () => {
        try { if (document.fullscreenElement) await document.exitFullscreen(); else await viewer.requestFullscreen(); }
        catch (_) { full.hidden = true; }
      };
      document.onfullscreenchange = () => {
        if (gen !== generation) return;
        full.textContent = document.fullscreenElement === viewer ? '전체 화면 닫기' : '전체 화면';
        lastWidth = -1; update();
      };
    }
    viewer.tabIndex = 0;
    viewer.onkeydown = ev => {
      if (ev.key === 'ArrowRight' || ev.key === 'PageDown') { ev.preventDefault(); next.click(); }
      if (ev.key === 'ArrowLeft' || ev.key === 'PageUp') { ev.preventDefault(); prev.click(); }
    };
    if ('ResizeObserver' in window) {
      resizeObserver = new ResizeObserver(() => {
        if (Math.abs(box.clientWidth - lastWidth) < 20) return;
        lastWidth = box.clientWidth; clearTimeout(timer); timer = setTimeout(update, 200);
      });
      resizeObserver.observe(box);
    }
    await draw();
  } catch (err) {
    fail();
  }
};

const initial = document.querySelector('#pdfViewer');
if (initial) window.startPdfViewer(initial.dataset.url);

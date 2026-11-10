let pdfViewerGeneration = 0;
let pdfDocumentTask = null;
let pdfRenderTask = null;

window.startPdfViewer = async function (url) {
  const generation = ++pdfViewerGeneration;
  if (pdfRenderTask) { pdfRenderTask.cancel(); pdfRenderTask = null; }
  if (pdfDocumentTask) { pdfDocumentTask.destroy(); pdfDocumentTask = null; }
  const viewer = document.querySelector('#pdfViewer');
  if (!viewer) return;
  const message = viewer.querySelector('.pdf-message');
  const canvas = viewer.querySelector('canvas');
  const pageLabel = viewer.querySelector('.pdf-page');
  const previous = viewer.querySelector('[data-pdf-previous]');
  const next = viewer.querySelector('[data-pdf-next]');
  const zoomIn = viewer.querySelector('[data-pdf-zoom-in]');
  const zoomOut = viewer.querySelector('[data-pdf-zoom-out]');
  let pageNumber = 1;
  let zoom = 1;
  try {
    const pdfjs = await import('./pdf.min.mjs');
    if (generation !== pdfViewerGeneration) return;
    pdfjs.GlobalWorkerOptions.workerSrc = new URL('./pdf.worker.min.mjs', import.meta.url).href;
    pdfDocumentTask = pdfjs.getDocument(url);
    const pdf = await pdfDocumentTask.promise;
    if (generation !== pdfViewerGeneration) return;
    async function renderPage() {
      if (pdfRenderTask) pdfRenderTask.cancel();
      message.textContent = '문서를 불러오는 중입니다.';
      const page = await pdf.getPage(pageNumber);
      if (generation !== pdfViewerGeneration) return;
      const base = page.getViewport({scale: 1});
      const available = Math.max(240, viewer.querySelector('.pdf-canvas').clientWidth - 24);
      const scale = Math.min(2, available / base.width) * zoom;
      const viewport = page.getViewport({scale});
      const outputScale = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(viewport.width * outputScale);
      canvas.height = Math.floor(viewport.height * outputScale);
      canvas.style.width = Math.floor(viewport.width) + 'px';
      canvas.style.height = Math.floor(viewport.height) + 'px';
      pageLabel.textContent = pageNumber + ' / ' + pdf.numPages;
      previous.disabled = pageNumber <= 1;
      next.disabled = pageNumber >= pdf.numPages;
      const task = page.render({canvasContext: canvas.getContext('2d'), viewport, transform: outputScale === 1 ? null : [outputScale, 0, 0, outputScale, 0, 0]});
      pdfRenderTask = task;
      try { await task.promise; if (generation === pdfViewerGeneration) message.textContent = ''; }
      catch (error) { if (error.name !== 'RenderingCancelledException') throw error; }
      finally { if (pdfRenderTask === task) pdfRenderTask = null; }
    }
    function update() { renderPage().catch(() => { if (generation === pdfViewerGeneration) message.textContent = '문서를 표시하지 못했습니다. 위의 PDF 새 창 열기 또는 PDF 저장을 이용해 주세요.'; }); }
    previous.onclick = () => { if (pageNumber > 1) { pageNumber--; update(); } };
    next.onclick = () => { if (pageNumber < pdf.numPages) { pageNumber++; update(); } };
    zoomIn.onclick = () => { zoom = Math.min(2.5, zoom + 0.25); update(); };
    zoomOut.onclick = () => { zoom = Math.max(0.5, zoom - 0.25); update(); };
    await renderPage();
  } catch (error) {
    if (generation === pdfViewerGeneration) message.textContent = '문서를 불러오지 못했습니다. 위의 PDF 새 창 열기 또는 PDF 저장을 이용해 주세요.';
  }
};

const initialViewer = document.querySelector("#pdfViewer");
if (initialViewer) window.startPdfViewer(initialViewer.dataset.url);

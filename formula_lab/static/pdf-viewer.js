/* Whole-document reading is independent of generation page selection. */
import {getDocument, GlobalWorkerOptions} from '/static/vendor/pdfjs/pdf.mjs';
GlobalWorkerOptions.workerSrc = '/static/vendor/pdfjs/pdf.worker.mjs';
const status = document.getElementById('status');
const container = document.getElementById('pages');
const query = new URLSearchParams(location.search);
const documentId = query.get('document');
const records = [], nearby = new Set(), queue = [];
let pdf, busy = false, currentPage = 1, zoom = 'fit', resizeTimer, framePending = false;
let lastWidth = document.documentElement.clientWidth;
function announce() {
  parent.postMessage({type: 'pdf-page', documentId, page: currentPage, pageCount: pdf.numPages}, location.origin);
}
function enqueue(record, priority = false) {
  if (!record.near || record.queued || record.task) return;
  record.queued = true; priority ? queue.unshift(record) : queue.push(record); pump();
}
async function pump() {
  if (busy) return;
  busy = true;
  while (queue.length) {
    const record = queue.shift(); record.queued = false;
    const width = Math.round(record.sheet.getBoundingClientRect().width);
    if (!record.near || width < 80 || record.renderedWidth === width) continue;
    const version = record.version;
    try {
      const page = await pdf.getPage(record.number);
      if (!record.near || record.version !== version) {enqueue(record); continue;}
      const normal = page.getViewport({scale: 1});
      record.sheet.style.aspectRatio = `${normal.width} / ${normal.height}`;
      const viewport = page.getViewport({scale: width / normal.width});
      const density = Math.min(devicePixelRatio || 1, 2);
      const canvas = document.createElement('canvas');
      canvas.width = Math.ceil(viewport.width * density); canvas.height = Math.ceil(viewport.height * density);
      canvas.setAttribute('role', 'img'); canvas.setAttribute('aria-label', `Original PDF page ${record.number}`);
      record.task = page.render({canvasContext: canvas.getContext('2d'), viewport,
        transform: density === 1 ? null : [density, 0, 0, density, 0, 0]});
      await record.task.promise;
      if (record.near && record.version === version) {
        record.sheet.replaceChildren(canvas); record.renderedWidth = width;
      }
    } catch (error) {
      if (error.name !== 'RenderingCancelledException' && record.near && record.version === version) {
        const message = document.createElement('p'); message.className = 'page-error';
        message.textContent = 'This page could not be rendered. Download the PDF to view it.';
        record.sheet.replaceChildren(message);
      }
    } finally {
      record.task = null;
      if (record.near && record.version !== version) enqueue(record);
    }
  }
  busy = false;
}
function release(record) {
  record.version++; record.task?.cancel(); record.renderedWidth = 0; record.sheet.replaceChildren();
}
function updateCurrent() {
  framePending = false;
  if (!pdf || !window.innerHeight) return;
  const point = Math.min(160, innerHeight * .25);
  let chosen = null, distance = Infinity;
  for (const record of nearby) {
    const rect = record.element.getBoundingClientRect();
    const nextDistance = rect.top <= point && rect.bottom > point ? 0 : Math.abs(rect.top - point);
    if (nextDistance < distance) {chosen = record; distance = nextDistance;}
  }
  if (chosen && chosen.number !== currentPage) {currentPage = chosen.number; announce();}
}
function jump(number) {
  if (!pdf || !Number.isInteger(number) || number < 1 || number > records.length) return;
  const record = records[number - 1];
  record.element.scrollIntoView({block: 'start'}); record.near = true; nearby.add(record);
  enqueue(record, true); currentPage = number; announce();
}
function resize() {
  if (!pdf || document.documentElement.clientWidth < 80) return;
  container.style.width = zoom === 'fit' ? '100%' : `${records[0].baseWidth * Number(zoom)}px`;
  for (const record of records) {
    record.version++; record.task?.cancel(); record.renderedWidth = 0;
    if (record.near) enqueue(record);
  }
}
try {
  pdf = await getDocument({url: documentId ? `/api/documents/${encodeURIComponent(documentId)}/file` : '/source.pdf',
    cMapUrl: '/static/vendor/pdfjs/cmaps/', cMapPacked: true,
    standardFontDataUrl: '/static/vendor/pdfjs/standard_fonts/', wasmUrl: '/static/vendor/pdfjs/wasm/',
    isEvalSupported: false}).promise;
  const first = await pdf.getPage(1), normal = first.getViewport({scale: 1});
  const fragment = document.createDocumentFragment();
  for (let number = 1; number <= pdf.numPages; number++) {
    const element = document.createElement('figure'); element.className = 'pdf-page';
    element.dataset.page = number;
    const label = document.createElement('figcaption'); label.className = 'page-label'; label.textContent = `Page ${number}`;
    const sheet = document.createElement('div'); sheet.className = 'pdf-sheet'; sheet.style.aspectRatio = `${normal.width} / ${normal.height}`;
    element.append(label, sheet); fragment.append(element);
    records.push({number, element, sheet, baseWidth: normal.width, near: false, queued: false, task: null, version: 0, renderedWidth: 0});
  }
  container.append(fragment); status.hidden = true;
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) {
      const record = records[Number(entry.target.dataset.page) - 1];
      record.near = entry.isIntersecting;
      if (record.near) {nearby.add(record); enqueue(record);}
      else {nearby.delete(record); release(record);}
    }
    updateCurrent();
  }, {rootMargin: '650px 0px'});
  records.forEach(record => observer.observe(record.element));
  addEventListener('scroll', () => {
    if (!framePending) {framePending = true; requestAnimationFrame(updateCurrent);}
  }, {passive: true});
  new ResizeObserver(() => {
    const width = document.documentElement.clientWidth;
    if (width < 80 || width === lastWidth) return;
    lastWidth = width; clearTimeout(resizeTimer); resizeTimer = setTimeout(resize, 100);
  }).observe(document.documentElement);
  addEventListener('message', event => {
    if (event.origin !== location.origin || event.source !== parent) return;
    if (event.data.type === 'go-to-page') jump(Number(event.data.page));
    if (event.data.type === 'pdf-zoom' && ['fit', '1', '1.25', '1.5'].includes(String(event.data.zoom))) {
      zoom = String(event.data.zoom); resize();
    }
  });
  announce();
  const initial = Number(query.get('page') || 1); if (initial > 1) jump(initial);
} catch {
  status.hidden = false; status.textContent = 'Unable to preview this PDF. Download it to view the document.';
}

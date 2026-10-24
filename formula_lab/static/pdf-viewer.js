/* Whole-document reading is independent of generation page selection. */
import {getDocument, GlobalWorkerOptions} from '/static/vendor/pdfjs/pdf.mjs';
GlobalWorkerOptions.workerSrc = '/static/vendor/pdfjs/pdf.worker.mjs';
const status = document.getElementById('status');
const container = document.getElementById('pages');
const query = new URLSearchParams(location.search);
const documentId = query.get('document');
const records = [], nearby = new Set(), queue = [];
const zoomLevels = ['fit', '1', '1.25', '1.5'];
let pdf, busy = false, currentPage = 1, zoom = zoomLevels.includes(query.get('zoom')) ? query.get('zoom') : 'fit';
let resizeTimer, pruneTimer, recoveryTimer, settleFrame, resizeAnchor, settleRequested = false, framePending = false, resizing = false, layoutWidth = 0;
function announce() {
  parent.postMessage({type: 'pdf-page', documentId, page: currentPage, pageCount: pdf.numPages}, location.origin);
}
function readingAnchor(point = 0) {
  let chosen, distance = Infinity;
  for (const record of records) {
    const rect = record.element.getBoundingClientRect();
    const nextDistance = rect.top <= point && rect.bottom > point ? 0 : Math.abs(rect.top - point);
    if (nextDistance < distance) {chosen = record; distance = nextDistance;}
  }
  if (!chosen) return null;
  const rect = chosen.sheet.getBoundingClientRect(), offset = point - rect.top;
  if (!rect.height) {
    const record = records[currentPage - 1] || chosen;
    return {record, point: 0, fraction: 0, edge: record.element.getBoundingClientRect().top - record.sheet.getBoundingClientRect().top, left: scrollX};
  }
  return {record: chosen, point, fraction: Math.max(0, Math.min(1, offset / rect.height)),
    edge: offset < 0 ? offset : offset > rect.height ? offset - rect.height : 0, left: scrollX};
}
function restoreAnchor(anchor) {
  if (!anchor) return;
  const rect = anchor.record.sheet.getBoundingClientRect();
  scrollTo(anchor.left, scrollY + rect.top + rect.height * anchor.fraction + anchor.edge - anchor.point);
}
function refreshNearby() {
  if (document.documentElement.clientWidth < 80) return;
  nearby.clear();
  for (const record of records) {
    const rect = record.element.getBoundingClientRect();
    record.near = rect.bottom > -650 && rect.top < innerHeight + 650;
    if (record.near) nearby.add(record);
  }
}
function enqueue(record, priority = false) {
  if (!record.near || record.queued || record.task) return;
  record.queued = true; priority ? queue.unshift(record) : queue.push(record); pump();
}
function scheduleNearby() {
  refreshNearby();
  for (const record of [...nearby].sort((a, b) => Math.abs(a.number - currentPage) - Math.abs(b.number - currentPage))) enqueue(record);
}
async function pump() {
  if (busy || resizing) return;
  busy = true;
  while (queue.length && !resizing) {
    const record = queue.shift(); record.queued = false;
    const width = Math.round(record.sheet.getBoundingClientRect().width);
    if (!record.near || width < 80 || (record.renderedWidth === width && record.sheet.querySelector('canvas'))) continue;
    const version = record.version;
    try {
      const page = await pdf.getPage(record.number);
      if (!record.near || record.version !== version) {enqueue(record); continue;}
      const normal = page.getViewport({scale: 1});
      if (Math.abs(record.ratio - normal.height / normal.width) > .0001) {
        const anchor = readingAnchor(); record.ratio = normal.height / normal.width;
        record.sheet.style.height = `${layoutWidth * record.ratio}px`; restoreAnchor(anchor); refreshNearby();
      }
      const viewport = page.getViewport({scale: width / normal.width});
      const density = Math.min(devicePixelRatio || 1, 2);
      // Render offscreen. The previous canvas stays visible, including during divider drags.
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
        if (!record.sheet.querySelector('canvas')) {
          const message = document.createElement('p'); message.className = 'page-error';
          message.textContent = 'This page could not be rendered. Download the PDF to view it.';
          record.sheet.replaceChildren(message);
        }
      }
    } finally {
      record.task = null;
      if (record.near && record.version !== version) enqueue(record);
    }
  }
  busy = false;
}
function pruneLater() {
  clearTimeout(pruneTimer);
  pruneTimer = setTimeout(() => {
    if (resizing) {pruneLater(); return;}
    refreshNearby();
    for (const record of records) {
      if (record.near || Math.abs(record.number - currentPage) <= 2) continue;
      record.version++; record.task?.cancel(); record.renderedWidth = 0; record.sheet.replaceChildren();
    }
  }, 500);
}
function updateCurrent() {
  framePending = false;
  if (!pdf || document.documentElement.clientWidth < 80) return;
  const anchor = readingAnchor(Math.min(160, innerHeight * .25));
  if (anchor && anchor.record.number !== currentPage) {currentPage = anchor.record.number; announce();}
  scheduleNearby(); pruneLater();
}
function jump(number) {
  if (!pdf || !Number.isInteger(number) || number < 1 || number > records.length) return;
  const record = records[number - 1];
  record.element.scrollIntoView({block: 'start'}); currentPage = number; announce();
  refreshNearby(); enqueue(record, true); scheduleNearby(); pruneLater();
}
function resize() {
  if (!pdf || document.documentElement.clientWidth < 80) return;
  // Heights remain fixed until here: capture the old vertical geometry before reflow.
  const anchor = resizing ? resizeAnchor : readingAnchor();
  container.style.width = zoom === 'fit' ? '100%' : `${records[0].baseWidth * Number(zoom)}px`;
  const width = container.getBoundingClientRect().width;
  if (Math.abs(width - layoutWidth) < .1) return;
  layoutWidth = width; resizeAnchor = anchor; resizing = true; clearTimeout(recoveryTimer);
  for (const record of records) {
    record.sheet.style.height = `${width * record.ratio}px`;
    record.version++; record.task?.cancel();
  }
  restoreAnchor(anchor); refreshNearby();
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => settleViewport(true), 120);
}
function settleViewport(redraw = false) {
  clearTimeout(resizeTimer);
  resizing = false; resizeAnchor = null;
  refreshNearby();
  // A final explicit redraw also refreshes iframe canvas layers after pointer capture ends.
  if (redraw) for (const record of nearby) {
    const rect = record.sheet.getBoundingClientRect();
    if (rect.bottom > 0 && rect.top < innerHeight) {
      record.version++; record.task?.cancel(); record.renderedWidth = 0;
    }
  }
  for (const record of queue) record.queued = false;
  queue.length = 0; scheduleNearby(); pump(); pruneLater();
  clearTimeout(recoveryTimer);
  recoveryTimer = setTimeout(() => {
    // Recheck the actual viewport independently of mouse/scroll/IntersectionObserver events.
    resize(); scheduleNearby(); pump();
  }, 300);
}
function syncViewport(settled = false) {
  settleRequested ||= settled;
  cancelAnimationFrame(settleFrame);
  settleFrame = requestAnimationFrame(() => {
    resize();
    if (settleRequested) {
      // Iframe layout can lag the outer grid by a frame. Read its final size once more.
      settleFrame = requestAnimationFrame(() => {resize(); settleRequested = false; settleViewport(true);});
    } else {
      clearTimeout(resizeTimer); resizeTimer = setTimeout(() => settleViewport(true), 120);
    }
  });
}
try {
  pdf = await getDocument({url: documentId ? `/api/documents/${encodeURIComponent(documentId)}/file` : '/source.pdf',
    cMapUrl: '/static/vendor/pdfjs/cmaps/', cMapPacked: true,
    standardFontDataUrl: '/static/vendor/pdfjs/standard_fonts/', wasmUrl: '/static/vendor/pdfjs/wasm/',
    isEvalSupported: false}).promise;
  const first = await pdf.getPage(1), normal = first.getViewport({scale: 1});
  const fragment = document.createDocumentFragment();
  container.style.width = zoom === 'fit' ? '100%' : `${normal.width * Number(zoom)}px`;
  layoutWidth = container.getBoundingClientRect().width;
  for (let number = 1; number <= pdf.numPages; number++) {
    const element = document.createElement('figure'); element.className = 'pdf-page'; element.dataset.page = number;
    const label = document.createElement('figcaption'); label.className = 'page-label'; label.textContent = `Page ${number}`;
    const sheet = document.createElement('div'); sheet.className = 'pdf-sheet'; sheet.style.height = `${layoutWidth * normal.height / normal.width}px`;
    element.append(label, sheet); fragment.append(element);
    records.push({number, element, sheet, baseWidth: normal.width, ratio: normal.height / normal.width,
      near: false, queued: false, task: null, version: 0, renderedWidth: 0});
  }
  container.append(fragment); status.hidden = true;
  const observer = new IntersectionObserver(() => {updateCurrent();}, {rootMargin: '650px 0px'});
  records.forEach(record => observer.observe(record.element));
  addEventListener('scroll', () => {
    if (!framePending) {framePending = true; requestAnimationFrame(updateCurrent);}
  }, {passive: true});
  new ResizeObserver(() => {
    const width = container.getBoundingClientRect().width;
    if (width >= 80 && Math.abs(width - layoutWidth) > .1) syncViewport();
  }).observe(container);
  addEventListener('resize', () => syncViewport());
  document.addEventListener('visibilitychange', () => {if (!document.hidden) syncViewport(true);});
  addEventListener('message', event => {
    if (event.origin !== location.origin || event.source !== parent) return;
    if (event.data.type === 'go-to-page') jump(Number(event.data.page));
    if (event.data.type === 'pdf-viewport') syncViewport(!!event.data.settled);
    if (event.data.type === 'pdf-zoom' && zoomLevels.includes(String(event.data.zoom)) && zoom !== String(event.data.zoom)) {
      zoom = String(event.data.zoom); resize();
    }
  });
  announce();
  jump(Number(query.get('page') || 1));
} catch {
  status.hidden = false; status.textContent = 'Unable to preview this PDF. Download it to view the document.';
}

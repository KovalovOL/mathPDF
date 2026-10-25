/* Whole-document reading is independent of generation page selection. */
import {getDocument, GlobalWorkerOptions, TextLayer} from '/static/vendor/pdfjs/pdf.mjs';
import {quotationRange, scrollToSource, cancelNavigation} from '/static/pdf-source.js';
GlobalWorkerOptions.workerSrc = '/static/vendor/pdfjs/pdf.worker.mjs';
const status = document.getElementById('status');
const container = document.getElementById('pages');
const query = new URLSearchParams(location.search);
const documentId = query.get('document');
const records = [], nearby = new Set(), queue = [];
const zoomLevels = ['fit', '1', '1.25', '1.5'];
let pdf, busy = false, currentPage = 1, zoom = zoomLevels.includes(query.get('zoom')) ? query.get('zoom') : 'fit';
let resizeTimer, pruneTimer, recoveryTimer, settleFrame, resizeAnchor, settleRequested = false, framePending = false, resizing = false, layoutWidth = 0;
let navigationVersion = 0, navigationRecord, pendingNavigation, highlightedRecord, highlightTimer;

function textViewport(record, page) {
  return page.getViewport({scale: record.sheet.getBoundingClientRect().width / page.getViewport({scale: 1}).width});
}
function resizeText(record) {
  if (!record.page || !record.textLayer) return;
  const viewport = textViewport(record, record.page);
  record.textContainer.style.setProperty('--total-scale-factor', viewport.scale);
  record.textLayer.update({viewport});
}
async function ensureText(record, page) {
  record.page = page;
  if (record.textLayer) {resizeText(record); return record.textLayer;}
  if (record.textPromise) return record.textPromise;
  const layerContainer = document.createElement('div'); layerContainer.className = 'textLayer';
  const viewport = textViewport(record, page);
  layerContainer.style.setProperty('--total-scale-factor', viewport.scale);
  layerContainer.style.setProperty('--scale-round-x', '1px');
  layerContainer.style.setProperty('--scale-round-y', '1px');
  const layer = new TextLayer({textContentSource: page.streamTextContent(), container: layerContainer, viewport});
  record.pendingText = layer;
  const promise = (async () => {
    try {
      await layer.render();
      if (record.pendingText !== layer) return null;
      record.textContainer = layerContainer; record.textLayer = layer;
      record.sheet.append(layerContainer); resizeText(record);
      return layer;
    } catch {return null;} // A PDF without extractable text still has its canvas preview.
    finally {
      if (record.pendingText === layer) {record.pendingText = null; record.textPromise = null;}
    }
  })();
  record.textPromise = promise;
  return promise;
}
function clearHighlight() {
  clearTimeout(highlightTimer);
  highlightedRecord?.sheet.classList.remove('source-page');
  highlightedRecord?.sheet.querySelector('.source-highlights')?.remove();
  highlightedRecord = null;
}
function highlightRange(record, range) {
  record.sheet.querySelector('.source-highlights')?.remove();
  if (!range) return null;
  const bounds = record.sheet.getBoundingClientRect(), overlay = document.createElement('div');
  overlay.className = 'source-highlights'; overlay.setAttribute('aria-hidden', 'true');
  let top = null;
  for (const rect of range.getClientRects()) {
    if (!rect.width || !rect.height) continue;
    const mark = document.createElement('span'); mark.className = 'source-highlight';
    Object.assign(mark.style, {left: `${rect.left - bounds.left}px`, top: `${rect.top - bounds.top}px`,
      width: `${rect.width}px`, height: `${rect.height}px`});
    overlay.append(mark); top = top === null ? rect.top : Math.min(top, rect.top);
  }
  record.sheet.append(overlay);
  return top;
}
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
    if (!record.near || width < 80) continue;
    if (record.renderedWidth === width && record.sheet.querySelector('canvas')) {
      if (record.page && !record.textLayer && !record.textPromise) ensureText(record, record.page).catch(() => null);
      continue;
    }
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
        const previous = record.sheet.querySelector('canvas');
        if (previous) previous.replaceWith(canvas); else record.sheet.prepend(canvas);
        record.sheet.querySelector('.page-error')?.remove(); record.renderedWidth = width;
        ensureText(record, page).catch(() => null);
      }
    } catch (error) {
      if (error.name !== 'RenderingCancelledException' && record.near && record.version === version) {
        if (!record.sheet.querySelector('canvas')) {
          const message = document.createElement('p'); message.className = 'page-error';
          message.textContent = 'This page could not be rendered. Download the PDF to view it.';
          record.sheet.prepend(message);
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
      const selection = getSelection();
      const selected = selection && !selection.isCollapsed && (record.sheet.contains(selection.anchorNode) ||
        record.sheet.contains(selection.focusNode) || selection.containsNode(record.sheet, true));
      if (record.near || record === navigationRecord || Math.abs(record.number - currentPage) <= 2 || selected) continue;
      record.version++; record.task?.cancel(); record.pendingText?.cancel();
      record.pendingText = null; record.textPromise = null; record.textLayer = null; record.textContainer = null;
      record.renderedWidth = 0; record.sheet.replaceChildren();
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
async function jump(number, {animated = false, quote = null} = {}) {
  if (!pdf || !Number.isInteger(number) || number < 1 || number > records.length) return;
  const record = records[number - 1];
  const version = ++navigationVersion;
  navigationRecord = record;
  cancelNavigation(); clearHighlight();
  let range = null;
  if (quote) {
    try {
      const page = await pdf.getPage(number), normal = page.getViewport({scale: 1});
      if (version !== navigationVersion) return;
      const anchor = readingAnchor(); record.ratio = normal.height / normal.width;
      record.sheet.style.height = `${layoutWidth * record.ratio}px`; restoreAnchor(anchor);
      const layer = await ensureText(record, page);
      if (version !== navigationVersion) return;
      if (layer) range = quotationRange(layer, quote);
    } catch { /* Page navigation remains available if text extraction fails. */ }
  }
  if (version !== navigationVersion) return;
  highlightedRecord = record;
  const fragmentTop = highlightRange(record, range);
  if (fragmentTop === null && animated) record.sheet.classList.add('source-page');
  highlightTimer = setTimeout(clearHighlight, 4500);
  const top = fragmentTop ?? record.element.getBoundingClientRect().top;
  await scrollToSource(scrollY + top - (fragmentTop === null ? 12 : Math.min(120, innerHeight * .2)), animated);
  if (version !== navigationVersion) return;
  currentPage = number; announce();
  navigationRecord = null;
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
    record.version++; record.task?.cancel(); record.pendingText?.cancel();
    record.pendingText = null; record.textPromise = null; resizeText(record);
  }
  navigationVersion++; navigationRecord = null; cancelNavigation(); clearHighlight();
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
  if (pendingNavigation) {
    const next = pendingNavigation; pendingNavigation = null;
    jump(next.page, next.options);
  }
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
  if (!documentId) throw new Error('No document selected.');
  pdf = await getDocument({url: `/api/documents/${encodeURIComponent(documentId)}/file`,
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
    if (!event.data || typeof event.data !== 'object') return;
    if (event.data.type === 'go-to-page') {
      navigationVersion++; navigationRecord = null; cancelNavigation();
      pendingNavigation = {page: Number(event.data.page), options: {
        animated: !!event.data.animated, quote: typeof event.data.quote === 'string' ? event.data.quote.slice(0, 1200) : null}};
      syncViewport(true);
    }
    if (event.data.type === 'pdf-viewport') syncViewport(!!event.data.settled);
    if (event.data.type === 'pdf-zoom' && zoomLevels.includes(String(event.data.zoom)) && zoom !== String(event.data.zoom)) {
      zoom = String(event.data.zoom); resize();
    }
  });
  for (const type of ['wheel', 'touchstart', 'pointerdown', 'keydown']) addEventListener(type, () => {
    navigationVersion++; navigationRecord = null; pendingNavigation = null; cancelNavigation();
  }, {passive: true});
  announce();
  jump(Number(query.get('page') || 1));
  parent.postMessage({type: 'pdf-ready', documentId}, location.origin);
} catch (error) {
  if (error.status === 401) parent.postMessage({type: 'session-expired'}, location.origin);
  status.hidden = false; status.textContent = 'Unable to preview this PDF. Download it to view the document.';
}

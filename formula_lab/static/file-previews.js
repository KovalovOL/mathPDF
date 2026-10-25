/* Lazy file previews use the same owner-protected originals as the workspace. */
import {createVisualCache, canvasBlob} from '/static/visual-cache.js';
let pdfModule;

export function createFilePreviews({request, userId, onAuthFailure}) {
  const cache = createVisualCache(userId), urls = new Set();
  let disposed = false, active = 0;
  const queue = [], targets = new Map(), pdfLoads = new Set(), controllers = new Set();
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      const file = targets.get(entry.target);
      if (!file) continue;
      observer.unobserve(entry.target); targets.delete(entry.target);
      queue.push({container: entry.target, file});
    }
    pump();
  }, {rootMargin: '250px 0px'});

  function canvasFor(width, height, filename) {
    const scale = Math.min(180 / width, 220 / height), density = Math.min(devicePixelRatio || 1, 2);
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.ceil(width * scale * density));
    canvas.height = Math.max(1, Math.ceil(height * scale * density));
    canvas.style.width = `${width * scale}px`; canvas.style.height = `${height * scale}px`;
    canvas.setAttribute('role', 'img'); canvas.setAttribute('aria-label', `Preview of ${filename}`);
    return {canvas, scale: scale * density};
  }

  async function renderPdf(container, file) {
    const {getDocument, GlobalWorkerOptions} = await (pdfModule ||= import('/static/vendor/pdfjs/pdf.mjs'));
    GlobalWorkerOptions.workerSrc = '/static/vendor/pdfjs/pdf.worker.mjs';
    const loading = getDocument({url: `/api/documents/${encodeURIComponent(file.id)}/file`,
      httpHeaders: {'X-MathPDF-User': userId}, isEvalSupported: false,
      cMapUrl: '/static/vendor/pdfjs/cmaps/', cMapPacked: true,
      standardFontDataUrl: '/static/vendor/pdfjs/standard_fonts/', wasmUrl: '/static/vendor/pdfjs/wasm/'});
    pdfLoads.add(loading);
    try {
      const pdf = await loading.promise;
      const page = await pdf.getPage(1), normal = page.getViewport({scale: 1});
      const {canvas, scale} = canvasFor(normal.width, normal.height, file.filename);
      const context = canvas.getContext('2d', {alpha: false});
      await page.render({canvasContext: context, viewport: page.getViewport({scale}), background: '#ffffff'}).promise;
      if (!disposed && container.isConnected) {
        canvas.setAttribute('aria-label', `First page of ${file.filename}`);
        container.replaceChildren(canvas);
      }
      const blob = await canvasBlob(canvas);
      if (blob && !disposed) await cache.put(file, 'preview', 1, {blob, width: canvas.width, height: canvas.height});
      page.cleanup();
    } finally {
      pdfLoads.delete(loading); await loading.destroy().catch(() => {});
    }
  }

  async function renderFile(container, file) {
    const controller = new AbortController(); controllers.add(controller);
    try {
      const response = await request(`/api/documents/${encodeURIComponent(file.id)}/file`, {signal: controller.signal});
      if (!response.ok) throw new Error('Preview unavailable.');
      let preview;
      if (file.media_type.startsWith('image/')) {
        const bitmap = await createImageBitmap(await response.blob());
        try {
          preview = canvasFor(bitmap.width, bitmap.height, file.filename).canvas;
          preview.getContext('2d').drawImage(bitmap, 0, 0, preview.width, preview.height);
        } finally {bitmap.close();}
      } else {
        const text = await response.text();
        preview = document.createElement('pre'); preview.className = 'file-text-excerpt';
        preview.textContent = text.slice(0, 1200) || 'Empty text file.';
        preview.setAttribute('aria-label', `Opening text of ${file.filename}`);
      }
      if (!disposed && container.isConnected) container.replaceChildren(preview);
      if (!disposed) {
        if (preview.tagName === 'CANVAS') {
          const blob = await canvasBlob(preview);
          if (blob) await cache.put(file, 'preview', 1, {blob});
        } else await cache.put(file, 'preview', 1, {text: preview.textContent});
      }
    } finally {controllers.delete(controller);}
  }

  async function renderCached(container, file) {
    const entry = await cache.get(file);
    if (disposed || !container.isConnected) return;
    if (entry?.blob) {
      const url = URL.createObjectURL(entry.blob); urls.add(url);
      const image = document.createElement('img'); image.src = url;
      image.alt = file.page_count ? `First page of ${file.filename}` : `Preview of ${file.filename}`;
      container.replaceChildren(image); container.dataset.cached = 'true'; return;
    }
    if (entry?.text !== undefined) {
      const text = document.createElement('pre'); text.className = 'file-text-excerpt'; text.textContent = entry.text;
      container.replaceChildren(text); container.dataset.cached = 'true'; return;
    }
    return file.media_type === 'application/pdf' ? renderPdf(container, file) : renderFile(container, file);
  }

  function pump() {
    while (!disposed && active < 2 && queue.length) {
      const {container, file} = queue.shift();
      if (!container.isConnected) continue;
      active++;
      const operation = renderCached(container, file);
      operation.catch(error => {
        if (disposed || !container.isConnected) return;
        container.textContent = 'Preview unavailable';
        if (error.status === 401 || error.status === 409) onAuthFailure();
      }).finally(() => {active--; pump();});
    }
  }

  return {
    observe(container, file) {if (!disposed) {targets.set(container, file); observer.observe(container);}},
    destroy() {
      disposed = true; observer.disconnect(); targets.clear(); queue.length = 0;
      for (const controller of controllers) controller.abort(); controllers.clear();
      for (const loading of pdfLoads) loading.destroy().catch(() => {}); pdfLoads.clear();
      for (const url of urls) URL.revokeObjectURL(url); urls.clear();
    },
  };
}

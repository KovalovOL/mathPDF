/* Whole-document reading is independent of generation page selection. */
import {
  getDocument,
  GlobalWorkerOptions,
  TextLayer,
} from "/static/vendor/pdfjs/pdf.mjs";
import { scrollToSource, cancelNavigation } from "/static/pdf-source.js";
import {
  createVisualCache,
  canvasBlob,
  cachedImage,
} from "/static/visual-cache.js";
import { createPdfAnnotations } from "/static/pdf-annotations.js";
class PdfViewer {
  #status;
  #container;
  #query;
  #documentId;
  #records;
  #nearby;
  #queue;
  #zoomLevels;
  #pdf;
  #sourceDocument;
  #renderDocument;
  #annotations;
  #visualCache;
  #loading;
  #disposed;
  #busy;
  #currentPage;
  #zoom;
  #resizeTimer;
  #pruneTimer;
  #recoveryTimer;
  #settleFrame;
  #resizeAnchor;
  #settleRequested;
  #framePending;
  #resizing;
  #layoutWidth;
  #navigationVersion;
  #navigationRecord;
  #pendingNavigation;
  constructor() {
    GlobalWorkerOptions.workerSrc = "/static/vendor/pdfjs/pdf.worker.mjs";
    this.#status = document.getElementById("status");
    this.#container = document.getElementById("pages");
    this.#query = new URLSearchParams(location.search);
    this.#documentId = this.#query.get("document");
    this.#records = [];
    this.#nearby = new Set();
    this.#queue = [];
    this.#zoomLevels = ["fit", "1", "1.25", "1.5"];
    this.#disposed = false;
    this.#busy = false;
    this.#currentPage = 1;
    this.#zoom = this.#zoomLevels.includes(this.#query.get("zoom"))
      ? this.#query.get("zoom")
      : "fit";
    this.#settleRequested = false;
    this.#framePending = false;
    this.#resizing = false;
    this.#layoutWidth = 0;
    this.#navigationVersion = 0;
  }
  #textViewport(record, page) {
    return page.getViewport({
      scale:
        record.sheet.getBoundingClientRect().width /
        page.getViewport({
          scale: 1,
        }).width,
    });
  }
  #resizeText(record) {
    if (!record.page || !record.textLayer) return;
    const viewport = this.#textViewport(record, record.page);
    record.textContainer.style.setProperty(
      "--total-scale-factor",
      viewport.scale,
    );
    record.textLayer.update({
      viewport,
    });
  }
  async #ensureText(record, page) {
    record.page = page;
    if (record.textLayer) {
      this.#resizeText(record);
      return record.textLayer;
    }
    if (record.textPromise) return record.textPromise;
    const layerContainer = document.createElement("div");
    layerContainer.className = "textLayer";
    const viewport = this.#textViewport(record, page);
    layerContainer.style.setProperty("--total-scale-factor", viewport.scale);
    layerContainer.style.setProperty("--scale-round-x", "1px");
    layerContainer.style.setProperty("--scale-round-y", "1px");
    const layer = new TextLayer({
      textContentSource: page.streamTextContent(),
      container: layerContainer,
      viewport,
    });
    record.pendingText = layer;
    const promise = (async () => {
      try {
        await layer.render();
        if (record.pendingText !== layer) return null;
        record.textContainer = layerContainer;
        record.textLayer = layer;
        record.sheet.append(layerContainer);
        this.#resizeText(record);
        return layer;
      } catch {
        return null;
      } finally {
        // A PDF without extractable text still has its canvas preview.
        if (record.pendingText === layer) {
          record.pendingText = null;
          record.textPromise = null;
        }
      }
    })();
    record.textPromise = promise;
    return promise;
  }
  #announce() {
    parent.postMessage(
      {
        type: "pdf-page",
        documentId: this.#documentId,
        page: this.#currentPage,
        pageCount: this.#pdf?.numPages || this.#sourceDocument.page_count,
      },
      location.origin,
    );
  }
  #cachePage(record) {
    if (
      !this.#visualCache ||
      record.number !== this.#currentPage ||
      !record.renderedWidth ||
      record.cachedWidth === record.renderedWidth
    )
      return;
    const canvas = record.sheet.querySelector("canvas");
    if (!canvas) return;
    record.cachedWidth = record.renderedWidth;
    canvasBlob(canvas)
      .then((blob) => {
        if (blob)
          return this.#visualCache.put(
            this.#renderDocument,
            "page",
            record.number,
            {
              blob,
              ratio: record.ratio,
              baseWidth: record.baseWidth,
            },
          );
      })
      .catch(() => {});
  }
  #touchCachedPage() {
    const record = this.#records[this.#currentPage - 1];
    if (!this.#visualCache || !record) return;
    this.#visualCache
      .get(this.#renderDocument, "page", record.number)
      .then((entry) => {
        // Another document/tab may have evicted this still-mounted canvas.
        if (!entry && record.number === this.#currentPage) {
          record.cachedWidth = 0;
          this.#cachePage(record);
        }
      })
      .catch(() => {});
  }
  #readingAnchor(point = 0) {
    let chosen,
      distance = Infinity;
    for (const record of this.#records) {
      const rect = record.element.getBoundingClientRect();
      const nextDistance =
        rect.top <= point && rect.bottom > point
          ? 0
          : Math.abs(rect.top - point);
      if (nextDistance < distance) {
        chosen = record;
        distance = nextDistance;
      }
    }
    if (!chosen) return null;
    const rect = chosen.sheet.getBoundingClientRect(),
      offset = point - rect.top;
    if (!rect.height) {
      const record = this.#records[this.#currentPage - 1] || chosen;
      return {
        record,
        point: 0,
        fraction: 0,
        edge:
          record.element.getBoundingClientRect().top -
          record.sheet.getBoundingClientRect().top,
        left: scrollX,
      };
    }
    return {
      record: chosen,
      point,
      fraction: Math.max(0, Math.min(1, offset / rect.height)),
      edge:
        offset < 0 ? offset : offset > rect.height ? offset - rect.height : 0,
      left: scrollX,
    };
  }
  #restoreAnchor(anchor) {
    if (!anchor) return;
    const rect = anchor.record.sheet.getBoundingClientRect();
    scrollTo(
      anchor.left,
      scrollY +
        rect.top +
        rect.height * anchor.fraction +
        anchor.edge -
        anchor.point,
    );
  }
  #refreshNearby() {
    if (document.documentElement.clientWidth < 80) return;
    this.#nearby.clear();
    for (const record of this.#records) {
      const rect = record.element.getBoundingClientRect();
      record.near = rect.bottom > -650 && rect.top < innerHeight + 650;
      if (record.near) this.#nearby.add(record);
    }
  }
  #enqueue(record, priority = false) {
    if (!record.near || record.queued || record.task) return;
    record.queued = true;
    priority ? this.#queue.unshift(record) : this.#queue.push(record);
    this.#pump();
  }
  #scheduleNearby() {
    this.#refreshNearby();
    for (const record of [...this.#nearby].sort(
      (a, b) =>
        Math.abs(a.number - this.#currentPage) -
        Math.abs(b.number - this.#currentPage),
    ))
      this.#enqueue(record);
  }
  async #pump() {
    if (!this.#pdf || this.#busy || this.#resizing) return;
    this.#busy = true;
    while (this.#queue.length && !this.#resizing) {
      const record = this.#queue.shift();
      record.queued = false;
      const width = Math.round(record.sheet.getBoundingClientRect().width);
      if (!record.near || width < 80) continue;
      if (
        record.renderedWidth === width &&
        record.sheet.querySelector("canvas")
      ) {
        if (record.page && !record.textLayer && !record.textPromise)
          this.#ensureText(record, record.page).catch(() => null);
        continue;
      }
      await this.#renderQueuedPage(record, width);
    }
    this.#busy = false;
  }
  async #renderQueuedPage(record, width) {
    const version = record.version;
    try {
      const page = await this.#pdf.getPage(record.number);
      if (!record.near || record.version !== version) {
        this.#enqueue(record);
        return;
      }
      const canvas = await this.#drawPageCanvas(record, page, width);
      if (record.near && record.version === version) {
        const previous = record.sheet.querySelector("canvas, .cached-page");
        if (previous) previous.replaceWith(canvas);
        else record.sheet.prepend(canvas);
        if (record.cachedUrl) {
          URL.revokeObjectURL(record.cachedUrl);
          record.cachedUrl = null;
        }
        record.sheet.querySelector(".page-error")?.remove();
        record.renderedWidth = width;
        this.#ensureText(record, page).catch(() => null);
        this.#cachePage(record);
      }
    } catch (error) {
      if (
        error.name !== "RenderingCancelledException" &&
        record.near &&
        record.version === version
      ) {
        if (!record.sheet.querySelector("canvas")) {
          const message = document.createElement("p");
          message.className = "page-error";
          message.textContent =
            "This page could not be rendered. Download the PDF to view it.";
          record.sheet.prepend(message);
        }
      }
    } finally {
      record.task = null;
      if (record.near && record.version !== version) this.#enqueue(record);
    }
  }
  #pruneLater() {
    clearTimeout(this.#pruneTimer);
    this.#pruneTimer = setTimeout(() => {
      if (this.#resizing) {
        this.#pruneLater();
        return;
      }
      this.#refreshNearby();
      for (const record of this.#records) {
        const selection = getSelection();
        const selected =
          selection &&
          !selection.isCollapsed &&
          (record.sheet.contains(selection.anchorNode) ||
            record.sheet.contains(selection.focusNode) ||
            selection.containsNode(record.sheet, true));
        if (
          record.near ||
          record === this.#navigationRecord ||
          Math.abs(record.number - this.#currentPage) <= 2 ||
          selected
        )
          continue;
        record.version++;
        record.task?.cancel();
        record.pendingText?.cancel();
        record.pendingText = null;
        record.textPromise = null;
        record.textLayer = null;
        record.textContainer = null;
        record.renderedWidth = 0;
        for (const child of [...record.sheet.children])
          if (!child.classList.contains("annotation-layer")) child.remove();
        if (record.cachedUrl) {
          URL.revokeObjectURL(record.cachedUrl);
          record.cachedUrl = null;
        }
      }
    }, 500);
  }
  #updateCurrent() {
    this.#framePending = false;
    if (!this.#records.length || document.documentElement.clientWidth < 80)
      return;
    const anchor = this.#readingAnchor(Math.min(160, innerHeight * 0.25));
    if (anchor && anchor.record.number !== this.#currentPage) {
      this.#currentPage = anchor.record.number;
      this.#announce();
      this.#touchCachedPage();
    }
    if (this.#records[this.#currentPage - 1])
      this.#cachePage(this.#records[this.#currentPage - 1]);
    this.#scheduleNearby();
    this.#pruneLater();
  }
  async #jump(number, { animated = false } = {}) {
    if (
      !this.#records.length ||
      !Number.isInteger(number) ||
      number < 1 ||
      number > this.#records.length
    )
      return;
    const record = this.#records[number - 1];
    const version = ++this.#navigationVersion;
    this.#navigationRecord = record;
    cancelNavigation();
    await scrollToSource(
      scrollY + record.element.getBoundingClientRect().top - 12,
      animated,
    );
    if (version !== this.#navigationVersion) return;
    this.#currentPage = number;
    this.#announce();
    this.#touchCachedPage();
    this.#navigationRecord = null;
    this.#refreshNearby();
    this.#enqueue(record, true);
    this.#scheduleNearby();
    this.#pruneLater();
  }
  #resize() {
    if (!this.#pdf || document.documentElement.clientWidth < 80) return;
    // Heights remain fixed until here: capture the old vertical geometry before reflow.
    const anchor = this.#resizing ? this.#resizeAnchor : this.#readingAnchor();
    this.#container.style.width =
      this.#zoom === "fit"
        ? "100%"
        : `${this.#records[0].baseWidth * Number(this.#zoom)}px`;
    const width = this.#container.getBoundingClientRect().width;
    if (Math.abs(width - this.#layoutWidth) < 0.1) return;
    this.#layoutWidth = width;
    this.#resizeAnchor = anchor;
    this.#resizing = true;
    clearTimeout(this.#recoveryTimer);
    for (const record of this.#records) {
      record.sheet.style.height = `${width * record.ratio}px`;
      record.version++;
      record.task?.cancel();
      record.pendingText?.cancel();
      record.pendingText = null;
      record.textPromise = null;
      this.#resizeText(record);
    }
    this.#navigationVersion++;
    this.#navigationRecord = null;
    cancelNavigation();
    this.#restoreAnchor(anchor);
    this.#refreshNearby();
    clearTimeout(this.#resizeTimer);
    this.#resizeTimer = setTimeout(() => this.#settleViewport(true), 120);
  }
  #settleViewport(redraw = false) {
    clearTimeout(this.#resizeTimer);
    this.#resizing = false;
    this.#resizeAnchor = null;
    this.#refreshNearby();
    // A final explicit redraw also refreshes iframe canvas layers after pointer capture ends.
    if (redraw)
      for (const record of this.#nearby) {
        const rect = record.sheet.getBoundingClientRect();
        if (rect.bottom > 0 && rect.top < innerHeight) {
          record.version++;
          record.task?.cancel();
          record.renderedWidth = 0;
        }
      }
    for (const record of this.#queue) record.queued = false;
    this.#queue.length = 0;
    this.#scheduleNearby();
    this.#pump();
    this.#pruneLater();
    clearTimeout(this.#recoveryTimer);
    this.#recoveryTimer = setTimeout(() => {
      // Recheck the actual viewport independently of mouse/scroll/IntersectionObserver events.
      this.#resize();
      this.#scheduleNearby();
      this.#pump();
    }, 300);
    if (this.#pendingNavigation) {
      const next = this.#pendingNavigation;
      this.#pendingNavigation = null;
      this.#jump(next.page, next.options);
    }
  }
  #syncViewport(settled = false) {
    this.#settleRequested ||= settled;
    cancelAnimationFrame(this.#settleFrame);
    this.#settleFrame = requestAnimationFrame(() => {
      this.#resize();
      if (this.#settleRequested) {
        // Iframe layout can lag the outer grid by a frame. Read its final size once more.
        this.#settleFrame = requestAnimationFrame(() => {
          this.#resize();
          this.#settleRequested = false;
          this.#settleViewport(true);
        });
      } else {
        clearTimeout(this.#resizeTimer);
        this.#resizeTimer = setTimeout(() => this.#settleViewport(true), 120);
      }
    });
  }
  async start() {
    try {
      if (!this.#documentId) throw new Error("No document selected.");
      const user = await MathPDFSession.ready;
      this.#sourceDocument = await MathPDFSession.api(
        `/api/documents/${encodeURIComponent(this.#documentId)}`,
      );
      this.#renderDocument = this.#sourceDocument;
      await this.#loadAnnotations();
      this.#loadDocument(user);
      const cached = await this.#createPageShells();
      this.#pdf = await this.#loading.promise;
      await this.#correctPageGeometry(cached);
      this.#installViewportObservers();
      this.#installParentMessages();
      this.#announce();
      this.#scheduleNearby();
      this.#pump(); // Initial navigation can queue pages before the PDF is ready.
      parent.postMessage(
        {
          type: "pdf-ready",
          documentId: this.#documentId,
        },
        location.origin,
      );
    } catch (error) {
      if (error.status === 401 || error.status === 409)
        parent.postMessage(
          {
            type: "session-expired",
          },
          location.origin,
        );
      this.#container.replaceChildren();
      this.#status.hidden = false;
      this.#status.textContent =
        "Unable to preview this PDF. Download it to view the document.";
    }
  }
  dispose() {
    this.#disposed = true;
    this.#annotations?.cancel();
    this.#loading?.destroy().catch(() => {});
    for (const record of this.#records)
      if (record.cachedUrl) URL.revokeObjectURL(record.cachedUrl);
  }
  async #drawPageCanvas(record, page, width) {
    const normal = page.getViewport({
      scale: 1,
    });
    this.#annotations?.attach(record, page);
    if (Math.abs(record.ratio - normal.height / normal.width) > 0.0001) {
      const anchor = this.#readingAnchor();
      record.ratio = normal.height / normal.width;
      record.sheet.style.height = `${this.#layoutWidth * record.ratio}px`;
      this.#restoreAnchor(anchor);
      this.#refreshNearby();
    }
    const viewport = page.getViewport({
      scale: width / normal.width,
    });
    const density = Math.min(devicePixelRatio || 1, 2);
    // Render offscreen. The previous canvas stays visible, including during divider drags.
    const canvas = document.createElement("canvas");
    canvas.width = Math.ceil(viewport.width * density);
    canvas.height = Math.ceil(viewport.height * density);
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", `Original PDF page ${record.number}`);
    record.task = page.render({
      canvasContext: canvas.getContext("2d"),
      viewport,
      transform: density === 1 ? null : [density, 0, 0, density, 0, 0],
    });
    await record.task.promise;
    return canvas;
  }
  #installParentMessages() {
    addEventListener("message", (event) => {
      if (event.origin !== location.origin || event.source !== parent) return;
      if (!event.data || typeof event.data !== "object") return;
      if (event.data.type === "go-to-page") {
        this.#navigationVersion++;
        this.#navigationRecord = null;
        cancelNavigation();
        this.#pendingNavigation = {
          page: Number(event.data.page),
          options: {
            animated: !!event.data.animated,
          },
        };
        this.#syncViewport(true);
      }
      if (event.data.type === "pdf-viewport")
        this.#syncViewport(!!event.data.settled);
      if (
        event.data.type === "pdf-zoom" &&
        this.#zoomLevels.includes(String(event.data.zoom)) &&
        this.#zoom !== String(event.data.zoom)
      ) {
        this.#zoom = String(event.data.zoom);
        this.#resize();
      }
    });
    for (const type of ["wheel", "touchstart", "pointerdown", "keydown"])
      addEventListener(
        type,
        () => {
          this.#navigationVersion++;
          this.#navigationRecord = null;
          this.#pendingNavigation = null;
          cancelNavigation();
        },
        {
          passive: true,
        },
      );
  }
  #installViewportObservers() {
    const observer = new IntersectionObserver(
      () => {
        this.#updateCurrent();
      },
      {
        rootMargin: "650px 0px",
      },
    );
    this.#records.forEach((record) => observer.observe(record.element));
    addEventListener(
      "scroll",
      () => {
        if (!this.#framePending) {
          this.#framePending = true;
          requestAnimationFrame(this.#updateCurrent.bind(this));
        }
      },
      {
        passive: true,
      },
    );
    new ResizeObserver(() => {
      const width = this.#container.getBoundingClientRect().width;
      if (width >= 80 && Math.abs(width - this.#layoutWidth) > 0.1)
        this.#syncViewport();
    }).observe(this.#container);
    addEventListener("resize", () => this.#syncViewport());
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) this.#syncViewport(true);
    });
  }
  async #correctPageGeometry(cached) {
    const first = await this.#pdf.getPage(1),
      actual = first.getViewport({
        scale: 1,
      }),
      anchor = this.#readingAnchor();
    for (const record of this.#records) {
      if (!cached.has(record.number)) {
        record.ratio = actual.height / actual.width;
        record.sheet.style.height = `${this.#layoutWidth * record.ratio}px`;
      }
      record.baseWidth = actual.width;
    }
    this.#restoreAnchor(anchor);
    this.#status.hidden = true;
  }
  async #createPageShells() {
    const cached = new Map(
      (await this.#visualCache.pages(this.#renderDocument)).map((entry) => [
        entry.page,
        entry,
      ]),
    );
    this.#container.dataset.cachedPages = String(cached.size);
    const normal = {
      width: cached.get(1)?.baseWidth || 612,
      height: 792,
    };
    const fragment = document.createDocumentFragment();
    this.#container.style.width =
      this.#zoom === "fit" ? "100%" : `${normal.width * Number(this.#zoom)}px`;
    this.#layoutWidth = this.#container.getBoundingClientRect().width;
    for (let number = 1; number <= this.#sourceDocument.page_count; number++) {
      this.#createPagePlaceholder(number, cached, normal, fragment);
    }
    this.#container.append(fragment);
    this.#status.hidden = cached.size > 0;
    await this.#jump(Number(this.#query.get("page") || 1));
    return cached;
  }
  #loadDocument(user) {
    this.#visualCache = createVisualCache(user.id);
    this.#loading = getDocument({
      url: `/api/documents/${encodeURIComponent(this.#renderDocument.id)}/file`,
      httpHeaders: {
        "X-MathPDF-User": user.id,
      },
      cMapUrl: "/static/vendor/pdfjs/cmaps/",
      cMapPacked: true,
      standardFontDataUrl: "/static/vendor/pdfjs/standard_fonts/",
      wasmUrl: "/static/vendor/pdfjs/wasm/",
      isEvalSupported: false,
    });
    this.#loading.promise.catch(() => {});
  }
  async #loadAnnotations() {
    try {
      const state = await MathPDFSession.api(
        `/api/documents/${encodeURIComponent(this.#documentId)}/annotations`,
      );
      if (state.base_document && state.annotations) {
        this.#renderDocument = state.base_document;
        this.#annotations = createPdfAnnotations({
          state,
          getDocumentId: () => this.#documentId,
          saved: (previous, result) => {
            this.#documentId = result.document.id;
            this.#sourceDocument = result.document;
            parent.postMessage(
              {
                type: "annotation-saved",
                documentId: previous,
                document: result.document,
              },
              location.origin,
            );
            this.#announce();
          },
          report: (message) =>
            parent.postMessage(
              {
                type: "annotation-error",
                documentId: this.#documentId,
                message,
              },
              location.origin,
            ),
        });
      }
    } catch (error) {
      parent.postMessage(
        {
          type: "annotation-error",
          documentId: this.#documentId,
          message: "Notes could not be loaded. Reload this PDF to edit them.",
        },
        location.origin,
      );
    }
  }
  #createPagePlaceholder(number, cached, normal, fragment) {
    const element = document.createElement("figure");
    element.className = "pdf-page";
    element.dataset.page = number;
    const label = document.createElement("figcaption");
    label.className = "page-label";
    label.textContent = `Page ${number}`;
    const entry = cached.get(number),
      ratio = entry?.ratio || normal.height / normal.width;
    const sheet = document.createElement("div");
    sheet.className = "pdf-sheet";
    sheet.style.height = `${this.#layoutWidth * ratio}px`;
    element.append(label, sheet);
    fragment.append(element);
    const record = {
      number,
      element,
      sheet,
      baseWidth: entry?.baseWidth || normal.width,
      ratio,
      near: false,
      queued: false,
      task: null,
      version: 0,
      renderedWidth: 0,
    };
    this.#installCachedPage(entry, record, number, sheet);
    this.#records.push(record);
  }
  #installCachedPage(entry, record, number, sheet) {
    if (entry?.bytes || entry?.blob) {
      const version = record.version;
      cachedImage(entry, `Original PDF page ${number}`).then((decoded) => {
        if (!decoded) {
          this.#visualCache.remove(this.#renderDocument, "page", number, entry);
          return;
        }
        if (
          this.#disposed ||
          record.version !== version ||
          sheet.querySelector("canvas")
        ) {
          URL.revokeObjectURL(decoded.url);
          return;
        }
        record.cachedUrl = decoded.url;
        decoded.image.className = "cached-page";
        sheet.prepend(decoded.image);
      });
    }
  }
}
const viewer = new PdfViewer();
viewer.start();
addEventListener("pagehide", () => viewer.dispose());

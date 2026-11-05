/* Lazy file previews use the same owner-protected originals as the workspace. */
import {
  createVisualCache,
  canvasBlob,
  cachedImage,
} from "/static/visual-cache.js";
let pdfModule;
class FilePreviews {
  constructor({ request, userId, onAuthFailure }) {
    this.#request = request;
    this.#userId = userId;
    this.#onAuthFailure = onAuthFailure;
    this.#cache = createVisualCache(this.#userId);
    this.#urls = new Set();
    this.#disposed = false;
    this.#active = 0;
    this.#queue = [];
    this.#targets = new Map();
    this.#pdfLoads = new Set();
    this.#controllers = new Set();
    this.#observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const file = this.#targets.get(entry.target);
          if (!file) continue;
          this.#observer.unobserve(entry.target);
          this.#targets.delete(entry.target);
          this.#queue.push({
            container: entry.target,
            file,
          });
        }
        this.#pump();
      },
      {
        rootMargin: "250px 0px",
      },
    );
  }
  #request;
  #userId;
  #onAuthFailure;
  #cache;
  #urls;
  #disposed;
  #active;
  #queue;
  #targets;
  #pdfLoads;
  #controllers;
  #observer;
  #canvasFor(width, height, filename) {
    const scale = Math.min(180 / width, 220 / height),
      density = Math.min(devicePixelRatio || 1, 2);
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.ceil(width * scale * density));
    canvas.height = Math.max(1, Math.ceil(height * scale * density));
    canvas.style.width = `${width * scale}px`;
    canvas.style.height = `${height * scale}px`;
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", `Preview of ${filename}`);
    return {
      canvas,
      scale: scale * density,
    };
  }
  async #renderPdf(container, file) {
    const { getDocument, GlobalWorkerOptions } = await (pdfModule ||=
      import("/static/vendor/pdfjs/pdf.mjs"));
    GlobalWorkerOptions.workerSrc = "/static/vendor/pdfjs/pdf.worker.mjs";
    const loading = getDocument({
      url: `/api/documents/${encodeURIComponent(file.id)}/file`,
      httpHeaders: {
        "X-MathPDF-User": this.#userId,
      },
      isEvalSupported: false,
      cMapUrl: "/static/vendor/pdfjs/cmaps/",
      cMapPacked: true,
      standardFontDataUrl: "/static/vendor/pdfjs/standard_fonts/",
      wasmUrl: "/static/vendor/pdfjs/wasm/",
    });
    this.#pdfLoads.add(loading);
    try {
      const pdf = await loading.promise;
      const [page, canvas, scale] = await this.#preparePdfPreview(pdf, file);
      const context = canvas.getContext("2d", {
        alpha: false,
      });
      await page.render({
        canvasContext: context,
        viewport: page.getViewport({
          scale,
        }),
        background: "#ffffff",
      }).promise;
      if (!this.#disposed && container.isConnected) {
        canvas.setAttribute("aria-label", `First page of ${file.filename}`);
        container.replaceChildren(canvas);
      }
      const blob = await canvasBlob(canvas);
      if (blob && !this.#disposed)
        await this.#cache.put(file, "preview", 1, {
          blob,
          width: canvas.width,
          height: canvas.height,
        });
      page.cleanup();
    } finally {
      this.#pdfLoads.delete(loading);
      await loading.destroy().catch(() => {});
    }
  }
  async #renderFile(container, file) {
    const controller = new AbortController();
    this.#controllers.add(controller);
    try {
      const response = await (0, this.#request)(
        `/api/documents/${encodeURIComponent(file.id)}/file`,
        {
          signal: controller.signal,
        },
      );
      if (!response.ok) throw new Error("Preview unavailable.");
      let preview;
      if (file.media_type.startsWith("image/")) {
        const bitmap = await createImageBitmap(await response.blob());
        try {
          preview = this.#canvasFor(
            bitmap.width,
            bitmap.height,
            file.filename,
          ).canvas;
          preview
            .getContext("2d")
            .drawImage(bitmap, 0, 0, preview.width, preview.height);
        } finally {
          bitmap.close();
        }
      } else {
        const text = await response.text();
        preview = document.createElement("pre");
        preview.className = "file-text-excerpt";
        preview.textContent = text.slice(0, 1200) || "Empty text file.";
        preview.setAttribute("aria-label", `Opening text of ${file.filename}`);
      }
      if (!this.#disposed && container.isConnected)
        container.replaceChildren(preview);
      await this.#storePreview(file, preview);
    } finally {
      this.#controllers.delete(controller);
    }
  }
  async #renderCached(container, file) {
    const entry = await this.#cache.get(file);
    if (this.#disposed || !container.isConnected) return;
    if (entry?.bytes || entry?.blob) {
      const decoded = await cachedImage(
        entry,
        file.page_count
          ? `First page of ${file.filename}`
          : `Preview of ${file.filename}`,
      );
      if (decoded) {
        if (this.#disposed || !container.isConnected) {
          URL.revokeObjectURL(decoded.url);
          return;
        }
        this.#urls.add(decoded.url);
        container.replaceChildren(decoded.image);
        container.dataset.cached = "true";
        return;
      }
      await this.#cache.remove(file, "preview", 1, entry);
    }
    if (entry?.text !== undefined) {
      const text = document.createElement("pre");
      text.className = "file-text-excerpt";
      text.textContent = entry.text;
      container.replaceChildren(text);
      container.dataset.cached = "true";
      return;
    }
    if (!this.#disposed && container.isConnected)
      return file.media_type === "application/pdf"
        ? this.#renderPdf(container, file)
        : this.#renderFile(container, file);
  }
  #pump() {
    while (!this.#disposed && this.#active < 2 && this.#queue.length) {
      const { container, file } = this.#queue.shift();
      if (!container.isConnected) continue;
      this.#active++;
      const operation = this.#renderCached(container, file);
      operation
        .catch((error) => {
          if (this.#disposed || !container.isConnected) return;
          container.textContent = "Preview unavailable";
          if (error.status === 401 || error.status === 409)
            (0, this.#onAuthFailure)();
        })
        .finally(() => {
          this.#active--;
          this.#pump();
        });
    }
  }
  get api() {
    return {
      observe: (...args) => this.#api_observe(...args),
      destroy: (...args) => this.#api_destroy(...args),
    };
  }
  #api_observe(container, file) {
    if (!this.#disposed) {
      this.#targets.set(container, file);
      this.#observer.observe(container);
    }
  }
  #api_destroy() {
    this.#disposed = true;
    this.#observer.disconnect();
    this.#targets.clear();
    this.#queue.length = 0;
    for (const controller of this.#controllers) controller.abort();
    this.#controllers.clear();
    for (const loading of this.#pdfLoads) loading.destroy().catch(() => {});
    this.#pdfLoads.clear();
    for (const url of this.#urls) URL.revokeObjectURL(url);
    this.#urls.clear();
  }
  async #preparePdfPreview(pdf, file) {
    const page = await pdf.getPage(1),
      normal = page.getViewport({
        scale: 1,
      });
    const { canvas, scale } = this.#canvasFor(
      normal.width,
      normal.height,
      file.filename,
    );
    return [page, canvas, scale];
  }
  async #storePreview(file, preview) {
    if (!this.#disposed) {
      if (preview.tagName === "CANVAS") {
        const blob = await canvasBlob(preview);
        if (blob)
          await this.#cache.put(file, "preview", 1, {
            blob,
          });
      } else
        await this.#cache.put(file, "preview", 1, {
          text: preview.textContent,
        });
    }
  }
}
export function createFilePreviews({ request, userId, onAuthFailure }) {
  return new FilePreviews({
    request,
    userId,
    onAuthFailure,
  }).api;
}

/* Editable marks over the immutable source, in unrotated PDF coordinates. */
import {
  annotationHistory,
  changedPages,
  hitMark,
  mergeTextRects,
} from "/static/pdf-annotation-model.js";
const NS = "http://www.w3.org/2000/svg";
const svg = (tag, attributes) => {
  const node = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attributes || {}))
    node.setAttribute(key, value);
  return node;
};
class PdfAnnotations {
  constructor({ state, getDocumentId, saved, report }) {
    this.#state = state;
    this.#getDocumentId = getDocumentId;
    this.#saved = saved;
    this.#report = report;
    this.#history = annotationHistory(this.#state.annotations.items);
    this.#pages = new Map();
    this.#tool = "select";
    this.#active = false;
    this.#width = 2;
    this.#color = "#2563eb";
    this.#saving = false;
    this.#gesture = undefined;
    this.#selected = [];
    this.#selectionFrame = undefined;
    this.#savePromise = undefined;
    this.#lastState = undefined;
    this.#colors = {
      pen: "#2563eb",
      highlight: "#facc15",
    };
    this.#post = (type, payload) =>
      parent.postMessage(
        {
          type,
          documentId: (0, this.#getDocumentId)(),
          ...payload,
        },
        location.origin,
      );
    this.#bindDocumentSelectionchange();
    this.#bindDocumentPointerup();
    this.#bindWindowMessage();
    this.#bindWindowKeydown();
    this.#emit();
  }
  #state;
  #getDocumentId;
  #saved;
  #report;
  #history;
  #pages;
  #tool;
  #active;
  #width;
  #color;
  #saving;
  #gesture;
  #selected;
  #selectionFrame;
  #savePromise;
  #lastState;
  #colors;
  #post;
  #emit() {
    const value = {
      loaded: true,
      active: this.#active,
      tool: this.#tool,
      color: this.#color,
      width: this.#width,
      saving: this.#saving,
      dirty: this.#history.dirty,
      canUndo: this.#history.canUndo,
      canRedo: this.#history.canRedo,
      baseDocumentId: this.#state.base_document.id,
      copyDocument: this.#state.copy_document,
    };
    const key = JSON.stringify(value);
    if (key === this.#lastState) return;
    this.#lastState = key;
    (0, this.#post)("annotation-state", value);
  }
  #draw(record, items = this.#history.items) {
    const group = record.annotationGroup;
    if (!group) return;
    group.replaceChildren(
      ...items
        .filter((mark) => mark.page === record.number)
        .map((mark) => {
          if (mark.kind === "highlight") {
            const node = svg("g", {
              fill: mark.color,
              "fill-opacity": ".28",
              class: "pdf-highlight",
            });
            for (const quad of mark.quads)
              node.append(
                svg("polygon", {
                  points: quad.map((p) => p.join(",")).join(" "),
                }),
              );
            return node;
          }
          if (mark.points.length === 1)
            return svg("circle", {
              cx: mark.points[0][0],
              cy: mark.points[0][1],
              r: mark.width / 2,
              fill: mark.color,
            });
          return svg("polyline", {
            points: mark.points.map((p) => p.join(",")).join(" "),
            fill: "none",
            stroke: mark.color,
            "stroke-width": mark.width,
            "stroke-linecap": "round",
            "stroke-linejoin": "round",
          });
        }),
    );
  }
  #update(before) {
    for (const number of changedPages(before, this.#history.items))
      if (this.#pages.has(number)) this.#draw(this.#pages.get(number));
    this.#emit();
  }
  #mode() {
    for (const record of this.#pages.values()) {
      record.annotationLayer.classList.toggle(
        "drawing",
        this.#active && !this.#saving && ["pen", "eraser"].includes(this.#tool),
      );
      record.annotationLayer.classList.toggle(
        "erasing",
        this.#tool === "eraser",
      );
    }
    this.#emit();
  }
  #viewport(record) {
    const normal = record.page.getViewport({
      scale: 1,
    });
    return record.page.getViewport({
      scale: record.sheet.getBoundingClientRect().width / normal.width,
    });
  }
  #point(record, event) {
    const box = record.sheet.getBoundingClientRect();
    return this.#viewport(record)
      .convertToPdfPoint(
        Math.max(0, Math.min(box.width, event.clientX - box.left)),
        Math.max(0, Math.min(box.height, event.clientY - box.top)),
      )
      .map((value) => Math.round(value * 10000) / 10000);
  }
  #finish(cancelled = false) {
    const current = this.#gesture;
    if (!current) return;
    this.#gesture = null;
    current.preview?.remove();
    if (current.record.annotationLayer.hasPointerCapture(current.pointer))
      current.record.annotationLayer.releasePointerCapture(current.pointer);
    const before = this.#history.items;
    if (!cancelled)
      this.#history.commit(
        current.mark ? [...before, current.mark] : current.items,
      );
    this.#draw(current.record);
    this.#update(before);
  }
  #move(record, event) {
    if (!this.#gesture || this.#gesture.pointer !== event.pointerId) return;
    event.preventDefault();
    const samples = event.getCoalescedEvents?.();
    for (const sample of samples?.length ? samples : [event]) {
      const next = this.#point(record, sample),
        scale = this.#viewport(record).scale;
      if (this.#gesture.mark) {
        const points = this.#gesture.mark.points,
          last = points.at(-1);
        if (
          Math.hypot(next[0] - last[0], next[1] - last[1]) * scale >= 0.7 &&
          points.length < 20000
        )
          points.push(next);
      } else {
        const filtered = this.#gesture.items.filter(
          (mark) =>
            mark.page !== record.number || !hitMark(mark, next, 7 / scale),
        );
        if (filtered.length !== this.#gesture.items.length) {
          this.#gesture.items = filtered;
          this.#draw(record, filtered);
        }
      }
    }
    if (this.#gesture.mark)
      this.#gesture.preview.setAttribute(
        "points",
        this.#gesture.mark.points.map((p) => p.join(",")).join(" "),
      );
  }
  #attach(record, page) {
    record.page = page;
    if (!record.annotationLayer) {
      const layer = this.#installAnnotationLayer(record, page);
      layer.addEventListener("pointerup", (event) => {
        this.#move(record, event);
        this.#finish();
      });
      layer.addEventListener("pointercancel", () => this.#finish(true));
      layer.addEventListener("lostpointercapture", () => this.#finish(true));
    }
    const normal = page.getViewport({
      scale: 1,
    });
    record.annotationLayer.setAttribute(
      "viewBox",
      `0 0 ${normal.width} ${normal.height}`,
    );
    record.annotationGroup.setAttribute(
      "transform",
      `matrix(${normal.transform.join(" ")})`,
    );
    this.#draw(record);
    this.#mode();
  }
  #captureSelection() {
    this.#selected = [];
    const selection = getSelection();
    if (!selection || selection.isCollapsed || !selection.rangeCount) return;
    const range = selection.getRangeAt(0);
    for (const record of this.#pages.values()) {
      this.#capturePageSelection(record, range);
    }
  }
  #highlight() {
    this.#captureSelection();
    if (!this.#selected.length) return;
    const added = this.#selected.map((mark) => ({
      id: crypto.randomUUID(),
      kind: "highlight",
      color: this.#colors.highlight,
      ...mark,
    }));
    const before = this.#history.items;
    this.#history.commit([...before, ...added]);
    getSelection().removeAllRanges();
    this.#selected = [];
    this.#update(before);
  }
  #editHistory(redo) {
    if (this.#saving) return;
    this.#finish(true);
    const before = this.#history.items;
    if (redo) this.#history.redo();
    else this.#history.undo();
    this.#update(before);
  }
  async #save() {
    if (this.#savePromise) return this.#savePromise;
    this.#finish();
    if (!this.#history.dirty) return this.#state;
    this.#saving = true;
    this.#mode();
    this.#savePromise = (async () => {
      try {
        const previous = (0, this.#getDocumentId)(),
          items = this.#history.items;
        const result = await MathPDFSession.api(
          `/api/documents/${encodeURIComponent(previous)}/annotations`,
          {
            method: "PUT",
            body: JSON.stringify({
              schema_version: 1,
              items,
              expected_revision: this.#state.revision,
            }),
            timeoutMs: 60000,
          },
        );
        this.#history.markSaved(items);
        this.#state = result;
        (0, this.#saved)(previous, result);
        return result;
      } finally {
        this.#saving = false;
        this.#savePromise = null;
        this.#mode();
      }
    })();
    return this.#savePromise;
  }
  async #command(data) {
    if (data.action === "diagnostic")
      return {
        document_id: (0, this.#getDocumentId)(),
        base_document_id: this.#state.base_document.id,
        revision: this.#state.revision,
        annotations: {
          schema_version: 1,
          items: this.#history.items,
        },
        dirty: this.#history.dirty,
        saving: this.#saving,
      };
    if (data.action === "save") return this.#save();
    if (this.#saving) return;
    return this.#applyEditingCommand(data);
  }
  #bindDocumentSelectionchange() {
    document.addEventListener("selectionchange", () => {
      cancelAnimationFrame(this.#selectionFrame);
      this.#selectionFrame = requestAnimationFrame(
        this.#captureSelection.bind(this),
      );
    });
  }
  #bindDocumentPointerup() {
    document.addEventListener("pointerup", () => {
      if (this.#active && this.#tool === "highlight" && !this.#saving)
        setTimeout(this.#highlight.bind(this), 0);
    });
  }
  #bindWindowMessage() {
    addEventListener("message", (event) => {
      if (
        event.origin !== location.origin ||
        event.source !== parent ||
        event.data?.type !== "annotation-command" ||
        event.data.documentId !== (0, this.#getDocumentId)()
      )
        return;
      const data = event.data;
      Promise.resolve(this.#command(data))
        .then((result) => {
          if (data.requestId)
            (0, this.#post)("annotation-result", {
              requestId: data.requestId,
              result,
            });
        })
        .catch((error) => {
          (0, this.#report)(error.message);
          if (data.requestId)
            (0, this.#post)("annotation-result", {
              requestId: data.requestId,
              error: error.message,
            });
        });
    });
  }
  #bindWindowKeydown() {
    addEventListener("keydown", (event) => {
      if (
        !(event.ctrlKey || event.metaKey) ||
        event.altKey ||
        event.target.closest?.("input,textarea,select,[contenteditable=true]")
      )
        return;
      const key = event.key.toLowerCase();
      if (key === "s") {
        event.preventDefault();
        this.#save().catch((error) => (0, this.#report)(error.message));
      } else if (
        key === "z" &&
        (this.#active || this.#history.canUndo || this.#history.canRedo)
      ) {
        event.preventDefault();
        this.#editHistory(event.shiftKey);
      } else if (key === "y" && this.#active) {
        event.preventDefault();
        this.#editHistory(true);
      }
    });
  }
  get api() {
    return {
      attach: this.#attach.bind(this),
      cancel: (...args) => this.#api_cancel(...args),
    };
  }
  #api_cancel() {
    return this.#finish(true);
  }
  #installAnnotationLayer(record, page) {
    const layer = svg("svg", {
        class: "annotation-layer",
        "aria-hidden": "true",
      }),
      group = svg("g");
    layer.append(group);
    record.sheet.append(layer);
    record.annotationLayer = layer;
    record.annotationGroup = group;
    this.#pages.set(record.number, record);
    layer.addEventListener("pointerdown", (event) =>
      this.#beginStroke(event, record, layer, page, group),
    );
    layer.addEventListener("pointermove", (event) => this.#move(record, event));
    return layer;
  }
  #beginStroke(event, record, layer, page, group) {
    if (
      !this.#active ||
      this.#saving ||
      event.button !== 0 ||
      !event.isPrimary ||
      !["pen", "eraser"].includes(this.#tool)
    )
      return;
    event.preventDefault();
    if (this.#gesture) this.#finish(true);
    const start = this.#point(record, event);
    this.#gesture = {
      record,
      pointer: event.pointerId,
      items: this.#history.items,
    };
    layer.setPointerCapture(event.pointerId);
    if (this.#tool === "pen") {
      if (this.#history.items.length >= 5000) {
        this.#finish(true);
        (0, this.#report)("This PDF has reached the annotation limit.");
        return;
      }
      this.#gesture.mark = {
        id: crypto.randomUUID(),
        kind: "ink",
        page: record.number,
        color: this.#color,
        width: this.#width / (page.userUnit || 1),
        points: [start],
      };
      this.#gesture.preview = svg("polyline", {
        points: start.join(","),
        fill: "none",
        stroke: this.#color,
        "stroke-width": this.#gesture.mark.width,
        "stroke-linecap": "round",
        "stroke-linejoin": "round",
      });
      group.append(this.#gesture.preview);
    } else this.#move(record, event);
  }
  #capturePageSelection(record, range) {
    const text = record.sheet.querySelector(".textLayer");
    if (!text) return;
    const box = record.sheet.getBoundingClientRect(),
      vp = this.#viewport(record),
      rectangles = [];
    const walker = document.createTreeWalker(text, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (!range.intersectsNode(node) || !node.textContent.trim()) continue;
      const part = document.createRange();
      part.selectNodeContents(node);
      if (range.startContainer === node) part.setStart(node, range.startOffset);
      if (range.endContainer === node) part.setEnd(node, range.endOffset);
      for (const rect of part.getClientRects()) {
        const left = Math.max(0, rect.left - box.left),
          right = Math.min(box.width, rect.right - box.left);
        const top = Math.max(0, rect.top - box.top),
          bottom = Math.min(box.height, rect.bottom - box.top);
        if (right - left < 0.2 || bottom - top < 0.2) continue;
        rectangles.push({
          left,
          right,
          top,
          bottom,
        });
      }
    }
    const quads = mergeTextRects(rectangles).map(
      ({ left, right, top, bottom }) =>
        [
          [left, top],
          [right, top],
          [right, bottom],
          [left, bottom],
        ].map((p) =>
          vp.convertToPdfPoint(...p).map((v) => Math.round(v * 10000) / 10000),
        ),
    );
    if (quads.length)
      this.#selected.push({
        page: record.number,
        quads,
      });
  }
  #applyEditingCommand(data) {
    if (data.action === "toggle") {
      if (
        !this.#state.document.original_document_id &&
        this.#state.copy_document
      ) {
        (0, this.#post)("annotation-open-copy", {
          document: this.#state.copy_document,
        });
        return;
      }
      this.#active = !this.#active;
      if (!this.#active) {
        this.#finish(true);
        this.#tool = "select";
      }
      this.#mode();
    } else if (data.action === "tool") {
      this.#finish(true);
      this.#active = true;
      this.#tool = data.tool;
      if (this.#tool === "pen" || this.#tool === "highlight")
        this.#color = this.#colors[this.#tool];
      this.#mode();
      if (this.#tool === "highlight") this.#highlight();
    } else if (data.action === "color") {
      this.#color = data.color;
      this.#colors[this.#tool === "highlight" ? "highlight" : "pen"] =
        this.#color;
      this.#emit();
    } else if (data.action === "width") {
      this.#width = data.width;
      this.#emit();
    } else if (data.action === "undo" || data.action === "redo")
      this.#editHistory(data.action === "redo");
  }
}
export function createPdfAnnotations({ state, getDocumentId, saved, report }) {
  return new PdfAnnotations({
    state,
    getDocumentId,
    saved,
    report,
  }).api;
}

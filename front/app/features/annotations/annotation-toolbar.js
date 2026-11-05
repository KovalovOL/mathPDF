/* Parent-side controls and save/generation choices; drawing stays in the PDF iframe. */
const $ = (id) => document.getElementById(id);
const icons = {
  select: "M4 3l15 9-7 1-3 7-5-17z",
  highlight: "M5 14l9-9 5 5-9 9H5v-5z M3 21h18",
  pen: "M4 20l4-1L20 7l-3-3L5 16l-1 4z M14 7l3 3",
  eraser: "M3 14l9-10 9 9-7 7H9l-6-6z M7 10l9 9 M14 20h7",
  undo: "M9 5L4 10l5 5 M4 10h9a6 6 0 010 12",
  redo: "M15 5l5 5-5 5 M20 10h-9a6 6 0 000 12",
  save: "M5 3h12l4 4v14H3V3h2z M7 3v6h10V3 M7 21v-8h10v8",
};
function iconButton(name, label) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "annotation-button";
  button.title = label;
  button.setAttribute("aria-label", label);
  const image = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  image.setAttribute("viewBox", "0 0 24 24");
  image.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(image.namespaceURI, "path");
  path.setAttribute("d", icons[name]);
  image.append(path);
  button.append(image);
  return button;
}
class AnnotationToolbar {
  constructor({
    activeDocument,
    documentFor,
    frameFor,
    onSaved,
    onOpenCopy,
    onChange,
    notifyViewport,
    report,
  }) {
    this.#activeDocument = activeDocument;
    this.#documentFor = documentFor;
    this.#frameFor = frameFor;
    this.#onSaved = onSaved;
    this.#onOpenCopy = onOpenCopy;
    this.#onChange = onChange;
    this.#notifyViewport = notifyViewport;
    this.#report = report;
    this.#states = new Map();
    this.#requests = new Map();
    this.#pendingOpen = new Set();
    this.#controls = new Map();
    this.#root = $("annotation-toolbar");
    this.#tools = $("annotation-tools");
    this.#toggle = $("annotate-pdf");
    this.#bindControlsMousedown();
    this.#save = iconButton("save", "Save PDF notes (Ctrl/Cmd+S)");
    this.#controls.set("save", this.#save);
    $("annotation-options").append(this.#save);
    this.#bindSaveClick();
    this.#bindToggleClick();
    this.#bindButtonMousedown();
    this.#bindAnnotationWidthChange();
    addEventListener("message", (event) =>
      this.#receiveAnnotationMessage(event),
    );
    this.#bindWindowKeydown();
  }
  #activeDocument;
  #documentFor;
  #frameFor;
  #onSaved;
  #onOpenCopy;
  #onChange;
  #notifyViewport;
  #report;
  #states;
  #requests;
  #pendingOpen;
  #controls;
  #root;
  #tools;
  #toggle;
  #save;
  #command(id, data) {
    const frame = (0, this.#frameFor)(id);
    if (!frame) return;
    frame.contentWindow.postMessage(
      {
        type: "annotation-command",
        documentId: id,
        ...data,
      },
      location.origin,
    );
  }
  #refresh() {
    const wasHidden = this.#root.hidden;
    const doc = (0, this.#activeDocument)(),
      state = this.#states.get(doc?.id),
      pdf = !!doc?.page_count;
    this.#toggle.hidden = !pdf;
    this.#toggle.disabled = !state?.loaded || state.saving;
    this.#toggle.setAttribute("aria-expanded", String(!!state?.active));
    this.#root.hidden = !pdf || !state?.active;
    for (const [name, button] of this.#controls) {
      button.disabled =
        !state?.loaded ||
        state.saving ||
        (name === "undo" && !state.canUndo) ||
        (name === "redo" && !state.canRedo) ||
        (name === "save" && !state.dirty);
      if (["select", "highlight", "pen", "eraser"].includes(name))
        button.setAttribute("aria-pressed", String(state?.tool === name));
    }
    if (state) {
      for (const swatch of $("annotation-color").querySelectorAll("button")) {
        swatch.setAttribute(
          "aria-pressed",
          String(swatch.dataset.color === state.color),
        );
        swatch.disabled = state.saving;
      }
      $("annotation-width").value = String(state.width);
      $("annotation-width").disabled = state.saving || state.tool !== "pen";
      $("annotation-status").textContent = state.saving
        ? "Saving…"
        : state.dirty
          ? "Unsaved notes"
          : doc.original_document_id
            ? "Saved"
            : "Original";
    }
    if (wasHidden !== this.#root.hidden) (0, this.#notifyViewport)(true);
  }
  async #saveNotes(id) {
    const state = this.#states.get(id);
    if (!state?.dirty)
      return {
        document: {
          id,
        },
      };
    const source = (0, this.#frameFor)(id)?.contentWindow;
    if (!source) throw new Error("Open this PDF to save its notes.");
    return new Promise((resolve, reject) => {
      const requestId = crypto.randomUUID(),
        timer = setTimeout(() => {
          this.#requests.delete(requestId);
          reject(
            new Error("Saving notes timed out. Your changes remain open."),
          );
        }, 65000);
      this.#requests.set(requestId, {
        source,
        resolve,
        reject,
        timer,
      });
      this.#command(id, {
        action: "save",
        requestId,
      });
    });
  }
  #choose(id, generation) {
    const dialog = $("annotation-choice");
    dialog.returnValue = "cancel";
    const filename = (0, this.#documentFor)(id)?.filename || "This PDF";
    $("annotation-choice-title").textContent = generation
      ? "Use unsaved PDF notes?"
      : "Save PDF notes before closing?";
    $("annotation-choice-message").textContent = generation
      ? `${filename} has unsaved notes. Send its unchanged original, or save and use the edited copy. Your notes stay open if you use the original.`
      : `${filename} has unsaved notes. Save them to its edited copy before closing?`;
    $("annotation-choice-discard").textContent = generation
      ? "Use original PDF"
      : "Discard changes";
    $("annotation-choice-save").textContent = generation
      ? "Save and use edited copy"
      : "Save and close";
    dialog.showModal();
    return new Promise((resolve) =>
      dialog.addEventListener("close", () => resolve(dialog.returnValue), {
        once: true,
      }),
    );
  }
  #bindControlsMousedown() {
    for (const [name, label] of [
      ["select", "Select text"],
      ["highlight", "Highlight selected text"],
      ["pen", "Draw"],
      ["eraser", "Erase stroke or highlight"],
      ["undo", "Undo notes"],
      ["redo", "Redo notes"],
    ]) {
      const button = iconButton(name, label);
      this.#controls.set(name, button);
      this.#tools.append(button);
      button.addEventListener("mousedown", (event) => event.preventDefault());
      button.addEventListener("click", () =>
        this.#command(
          (0, this.#activeDocument)()?.id,
          ["undo", "redo"].includes(name)
            ? {
                action: name,
              }
            : {
                action: "tool",
                tool: name,
              },
        ),
      );
    }
  }
  #bindSaveClick() {
    this.#save.addEventListener("click", () =>
      this.#saveNotes((0, this.#activeDocument)()?.id).catch((error) =>
        (0, this.#report)(error.message),
      ),
    );
  }
  #bindToggleClick() {
    this.#toggle.addEventListener("click", () =>
      this.#command((0, this.#activeDocument)()?.id, {
        action: "toggle",
      }),
    );
  }
  #bindButtonMousedown() {
    for (const swatch of $("annotation-color").querySelectorAll("button")) {
      swatch.addEventListener("mousedown", (event) => event.preventDefault());
      swatch.addEventListener("click", () =>
        this.#command((0, this.#activeDocument)()?.id, {
          action: "color",
          color: swatch.dataset.color,
        }),
      );
    }
  }
  #bindAnnotationWidthChange() {
    $("annotation-width").addEventListener("change", () =>
      this.#command((0, this.#activeDocument)()?.id, {
        action: "width",
        width: Number($("annotation-width").value),
      }),
    );
  }
  #bindWindowKeydown() {
    addEventListener("keydown", (event) => {
      if (
        !(event.ctrlKey || event.metaKey) ||
        event.altKey ||
        !(0, this.#activeDocument)()?.page_count
      )
        return;
      const key = event.key.toLowerCase(),
        id = (0, this.#activeDocument)().id,
        state = this.#states.get(id);
      if (key === "s" && state?.loaded) {
        event.preventDefault();
        this.#saveNotes(id).catch((error) => (0, this.#report)(error.message));
        return;
      }
      if (
        event.target.closest?.(
          "input,textarea,select,[contenteditable=true]",
        ) ||
        !(state?.active || state?.canUndo || state?.canRedo) ||
        !event.target.closest?.("#document-pane")
      )
        return;
      if (key === "z" || key === "y") {
        event.preventDefault();
        this.#command(id, {
          action: key === "y" || event.shiftKey ? "redo" : "undo",
        });
      }
    });
  }
  get api() {
    return {
      diagnosticContext: (...args) => this.#api_diagnosticContext(...args),
      refresh: this.#refresh.bind(this),
      dirty: (...args) => this.#api_dirty(...args),
      anyDirty: (...args) => this.#api_anyDirty(...args),
      dirtyDocuments: (...args) => this.#api_dirtyDocuments(...args),
      saveAll: (...args) => this.#api_saveAll(...args),
      forget: (...args) => this.#api_forget(...args),
      close: (...args) => this.#api_close(...args),
      prepare: (...args) => this.#api_prepare(...args),
    };
  }
  async #api_diagnosticContext() {
    return Promise.all(
      [...this.#states]
        .filter(([, state]) => state.dirty || state.saving)
        .slice(0, 12)
        .map(([id, state]) => this.#diagnosticRequest(id, state)),
    );
  }
  #api_dirty(id) {
    return !!this.#states.get(id)?.dirty;
  }
  #api_anyDirty() {
    return [...this.#states.values()].some(
      (state) => state.dirty || state.saving,
    );
  }
  #api_dirtyDocuments() {
    return [...this.#states]
      .filter(([, state]) => state.dirty || state.saving)
      .map(([id]) => id);
  }
  async #api_saveAll() {
    for (const id of this.#api_dirtyDocuments()) await this.#saveNotes(id);
  }
  #api_forget(id) {
    return this.#states.delete(id);
  }
  async #api_close(id) {
    if (!this.#states.get(id)?.dirty) return id;
    const answer = await this.#choose(id, false);
    if (answer === "save") return (await this.#saveNotes(id)).document.id;
    return answer === "discard" ? id : null;
  }
  async #api_prepare(request) {
    const selections = [
      {
        id: request.document_id,
        replace: (id) => {
          request.document_id = id;
        },
      },
      ...(request.context || []).map((entry) => ({
        id: entry.document_id,
        replace: (id) => {
          entry.document_id = id;
        },
      })),
    ];
    for (const entry of selections) {
      const state = this.#states.get(entry.id);
      if (!state?.dirty) continue;
      const answer = await this.#choose(entry.id, true);
      if (answer === "save")
        entry.replace((await this.#saveNotes(entry.id)).document.id);
      else if (answer === "discard") entry.replace(state.baseDocumentId);
      else return null;
    }
    return request;
  }
  #receiveAnnotationMessage(event) {
    const data = event.data;
    if (
      event.origin !== location.origin ||
      !data?.type?.startsWith("annotation-")
    )
      return;
    if (data.type === "annotation-result") {
      const pending = this.#requests.get(data.requestId);
      if (!pending || pending.source !== event.source) return;
      this.#requests.delete(data.requestId);
      clearTimeout(pending.timer);
      if (data.error) pending.reject(new Error(data.error));
      else pending.resolve(data.result);
      return;
    }
    if (event.source !== (0, this.#frameFor)(data.documentId)?.contentWindow)
      return;
    this.#receiveAnnotationState(data);
  }
  #diagnosticRequest(id, state) {
    return new Promise((resolve) => {
      const frame = (0, this.#frameFor)(id);
      if (!frame)
        return resolve({
          document_id: id,
          ...state,
          _unavailable: true,
        });
      const requestId = crypto.randomUUID(),
        timer = setTimeout(() => {
          this.#requests.delete(requestId);
          resolve({
            document_id: id,
            ...state,
            _unavailable: true,
          });
        }, 1200);
      this.#requests.set(requestId, {
        source: frame.contentWindow,
        timer,
        resolve,
        reject: () =>
          resolve({
            document_id: id,
            _unavailable: true,
          }),
      });
      this.#command(id, {
        action: "diagnostic",
        requestId,
      });
    });
  }
  #receiveAnnotationState(data) {
    if (data.type === "annotation-state") {
      this.#states.set(data.documentId, data);
      this.#refresh();
      (0, this.#onChange)();
      if (this.#pendingOpen.delete(data.documentId) && !data.active)
        this.#command(data.documentId, {
          action: "toggle",
        });
    } else if (data.type === "annotation-saved") {
      const previous = this.#states.get(data.documentId);
      this.#states.delete(data.documentId);
      this.#states.set(data.document.id, {
        ...previous,
        dirty: false,
        copyDocument: data.document,
      });
      (0, this.#onSaved)(data.documentId, data.document);
      this.#refresh();
    } else if (data.type === "annotation-open-copy") {
      this.#pendingOpen.add(data.document.id);
      Promise.resolve((0, this.#onOpenCopy)(data.document))
        .then(() => {
          const state = this.#states.get(data.document.id);
          if (
            state?.loaded &&
            this.#pendingOpen.delete(data.document.id) &&
            !state.active
          )
            this.#command(data.document.id, {
              action: "toggle",
            });
        })
        .catch((error) => (0, this.#report)(error.message));
    } else if (data.type === "annotation-error")
      (0, this.#report)(data.message);
  }
}
export function createAnnotationToolbar({
  activeDocument,
  documentFor,
  frameFor,
  onSaved,
  onOpenCopy,
  onChange,
  notifyViewport,
  report,
}) {
  return new AnnotationToolbar({
    activeDocument,
    documentFor,
    frameFor,
    onSaved,
    onOpenCopy,
    onChange,
    notifyViewport,
    report,
  }).api;
}

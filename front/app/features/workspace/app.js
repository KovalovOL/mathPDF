class WorkspaceController {
  constructor() {
    this.#initializeWorkspaceState();
    this.#bindDocumentActions();
    this.#bindGenerationActions();
    this.#bindRenameActions();
  }
  #$;
  #documents;
  #views;
  #reading;
  #sets;
  #contextChoices;
  #pendingUploads;
  #openDocumentIds;
  #activeDocumentId;
  #activeSetId;
  #config;
  #generationActive;
  #generationPreparing;
  #setEpoch;
  #saveIntent;
  #notes;
  #generationController;
  #lastGenerationSelection;
  #statusTimer;
  #practiceObserver;
  #viewportNotice;
  #viewportSettled;
  #layout;
  #initializing;
  #preferencePrefix;
  #reviewUI;
  #limitDialog;
  #wireFlashcard;
  #studyItemsView;
  #difficultyDescriptions;
  #nameDialog;
  #el(tag, className, text) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined) item.textContent = text;
    return item;
  }
  #button(text, className, action, label) {
    const item = this.#el("button", className, text);
    item.type = "button";
    if (label) item.setAttribute("aria-label", label);
    if (action) item.addEventListener("click", action);
    return item;
  }
  #message(text, error = false, duration = 6000) {
    clearTimeout(this.#statusTimer);
    (0, this.#$)("message").hidden = !text;
    (0, this.#$)("message").textContent = text;
    (0, this.#$)("message").className =
      `status-message${error ? " error" : ""}`;
    if (duration && text && !error)
      this.#statusTimer = setTimeout(() => {
        (0, this.#$)("message").hidden = true;
      }, duration);
  }
  async #api(path, options = {}) {
    return MathPDFSession.api(path, options);
  }
  async #action(operation) {
    try {
      await operation();
    } catch (error) {
      this.#message(error.message, true, 10000);
    }
  }
  #preference(key, value) {
    if (!this.#preferencePrefix) return;
    try {
      if (value === undefined)
        return localStorage.getItem(`${this.#preferencePrefix}${key}`);
      localStorage.setItem(`${this.#preferencePrefix}${key}`, String(value));
    } catch {}
  }
  #fileUrl(id, download = false) {
    return `/api/documents/${encodeURIComponent(id)}/file${download ? "?download=true" : ""}`;
  }
  #readState(id) {
    if (!this.#reading.has(id)) {
      let stored;
      try {
        stored = JSON.parse(this.#preference(`reading-${id}`));
      } catch {}
      this.#reading.set(id, {
        page:
          Number.isInteger(stored?.page) && stored.page > 0 ? stored.page : 1,
        zoom: ["fit", "1", "1.25", "1.5"].includes(stored?.zoom)
          ? stored.zoom
          : "fit",
      });
    }
    return this.#reading.get(id);
  }
  #makeTab(text, selected, operation, unsaved = false) {
    const tab = this.#button("", "tab", operation);
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    tab.title = text + (unsaved ? " · Unsaved" : "");
    tab.append(this.#el("span", "", text));
    if (unsaved) {
      const mark = this.#el("span", "unsaved-mark");
      mark.setAttribute("aria-label", "Unsaved");
      tab.append(mark);
    }
    return tab;
  }
  #closableTab(text, selected, operation, closeOperation, unsaved = false) {
    const wrapper = this.#el("div", "closable-tab");
    wrapper.setAttribute("role", "presentation");
    const tab = this.#makeTab(text, selected, operation, unsaved);
    const close = this.#button(
      "×",
      "tab-close",
      closeOperation,
      `Close ${text}`,
    );
    close.title = `Close ${text}`;
    wrapper.append(tab, close);
    return wrapper;
  }
  #wireTabs(container) {
    container.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key))
        return;
      const tabs = [...container.querySelectorAll('[role="tab"]')];
      const current = tabs.indexOf(document.activeElement);
      if (current < 0) return;
      event.preventDefault();
      const index =
        event.key === "Home"
          ? 0
          : event.key === "End"
            ? tabs.length - 1
            : (current + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) %
              tabs.length;
      tabs[index].click();
      requestAnimationFrame(() =>
        container.querySelector('[aria-selected="true"]')?.focus(),
      );
    });
  }
  #renderDocumentTabs() {
    (0, this.#$)("document-tabs").replaceChildren(
      ...this.#openDocumentIds.map((id) => {
        const doc = this.#documents.get(id) || this.#pendingUploads.get(id);
        const wrapper = this.#closableTab(
          doc.filename,
          id === this.#activeDocumentId,
          () => this.#action(() => this.#openDocument(id)),
          () => this.#action(() => this.#closeDocument(id)),
          this.#pendingUploads.has(id) || this.#notes?.dirty(id),
        );
        wrapper
          .querySelector('[role="tab"]')
          .setAttribute("aria-controls", `document-view-${id}`);
        return wrapper;
      }),
    );
    (0, this.#$)("document-tabs")
      .querySelector('[aria-selected="true"]')
      ?.closest(".closable-tab")
      .scrollIntoView({
        block: "nearest",
        inline: "nearest",
      });
    this.#preference(
      "open-files",
      JSON.stringify(
        this.#openDocumentIds.filter((id) => this.#documents.has(id)),
      ),
    );
  }
  #updateDocumentToolbar() {
    const doc = this.#documents.get(this.#activeDocumentId);
    (0, this.#$)("document-toolbar").hidden = !doc;
    if (!doc) {
      this.#notes?.refresh();
      return;
    }
    const isPdf = doc.media_type === "application/pdf",
      state = this.#readState(doc.id);
    (0, this.#$)("pdf-controls").hidden = !isPdf;
    (0, this.#$)("file-type").hidden = isPdf;
    (0, this.#$)("file-type").textContent = doc.media_type.startsWith("image/")
      ? "Image"
      : doc.media_type === "text/markdown"
        ? "Markdown"
        : "Text";
    (0, this.#$)("download-file").href = this.#fileUrl(doc.id, true);
    (0, this.#$)("download-file").download = doc.filename;
    if (isPdf) {
      (0, this.#$)("page").value = state.page;
      (0, this.#$)("page").max = doc.page_count;
      (0, this.#$)("page-count").textContent = `/ ${doc.page_count}`;
      (0, this.#$)("zoom").value = state.zoom;
      (0, this.#$)("previous-page").disabled = state.page <= 1;
      (0, this.#$)("next-page").disabled = state.page >= doc.page_count;
    }
    this.#notes?.refresh();
  }
  async #openDocument(id, targetPage, sourceRef = null) {
    const doc = this.#documents.get(id) || this.#pendingUploads.get(id);
    if (!doc) throw new Error("This source file is not available.");
    if (!this.#initializing || sourceRef)
      this.#layout?.showSource({
        scroll: !!sourceRef,
      });
    const state = this.#readState(id);
    if (targetPage !== undefined) {
      if (
        !doc.page_count ||
        !Number.isInteger(targetPage) ||
        targetPage < 1 ||
        targetPage > doc.page_count
      )
        throw new Error("That PDF page does not exist.");
      state.page = targetPage;
    }
    if (!this.#openDocumentIds.includes(id)) this.#openDocumentIds.push(id);
    this.#activeDocumentId = id;
    if (this.#documents.has(id)) this.#preference("active-file", id);
    (0, this.#$)("document-views").querySelector(".document-empty")?.remove();
    for (const [viewId, view] of this.#views) view.hidden = viewId !== id;
    let view = this.#views.get(id);
    if (!view) {
      [view] = this.#createDocumentView(doc, id, state);
    }
    if (this.#pendingUploads.has(id)) this.#renderUploadState(id);
    view.hidden = false;
    if (targetPage !== undefined) {
      const iframe = view.querySelector("iframe");
      if (iframe) {
        const navigation = {
          type: "go-to-page",
          page: targetPage,
          animated: !!sourceRef,
        };
        if (iframe.dataset.ready)
          iframe.contentWindow.postMessage(navigation, location.origin);
        else iframe.pendingNavigation = navigation;
      }
    }
    this.#renderDocumentTabs();
    this.#updateDocumentToolbar();
    this.#notifyPdfViewport(true);
  }
  #jumpPage(page) {
    return this.#openDocument(this.#activeDocumentId, page);
  }
  #renderUploadState(id) {
    const pending = this.#pendingUploads.get(id),
      content = this.#views.get(id)?.querySelector(".upload-state");
    if (!pending || !content) return;
    content.replaceChildren(
      this.#el("p", "", pending.filename),
      this.#el(
        "p",
        pending.error ? "error" : "field-note",
        pending.error || "Saving to server…",
      ),
    );
    if (pending.error)
      content.append(
        this.#button("Retry upload", "secondary", () =>
          this.#action(() => this.#saveUpload(id)),
        ),
      );
  }
  #showEmptyDocuments() {
    this.#activeDocumentId = null;
    for (const view of this.#views.values()) view.hidden = true;
    (0, this.#$)("document-views").querySelector(".document-empty")?.remove();
    const empty = this.#el("div", "document-empty");
    empty.append(
      this.#el(
        "p",
        "",
        this.#documents.size
          ? "No open files."
          : "Upload a PDF to start studying.",
      ),
      this.#button("Upload PDF", "", this.#chooseFiles.bind(this)),
    );
    if (this.#documents.size)
      empty.append(
        this.#button("Open saved files", "secondary", () =>
          this.#action(this.#showFiles.bind(this)),
        ),
      );
    (0, this.#$)("document-views").append(empty);
    this.#renderDocumentTabs();
    this.#updateDocumentToolbar();
  }
  async #closeDocument(id) {
    if (!this.#openDocumentIds.includes(id)) return;
    if (this.#pendingUploads.has(id)) {
      const pending = this.#pendingUploads.get(id);
      const dialog = (0, this.#$)("close-file-dialog");
      dialog.returnValue = "";
      (0, this.#$)("close-file-message").textContent =
        `${pending.filename} has not been saved to the server. Close this file and cancel its upload?`;
      dialog.showModal();
      const discard = await new Promise((resolve) =>
        dialog.addEventListener(
          "close",
          () => resolve(dialog.returnValue === "discard"),
          {
            once: true,
          },
        ),
      );
      if (!discard) return;
      // An upload can finish while the confirmation is open; never delete a saved file.
      this.#pendingUploads.get(id)?.controller?.abort();
      this.#pendingUploads.delete(id);
      id = pending.savedId || id;
    }
    if (this.#documents.has(id)) {
      id = await this.#notes.close(id);
      if (!id) return;
    }
    const index = this.#openDocumentIds.indexOf(id);
    if (index < 0) return;
    this.#openDocumentIds.splice(index, 1);
    this.#views.get(id)?.remove();
    this.#views.delete(id);
    this.#notes?.forget(id);
    if (this.#activeDocumentId === id) {
      const next =
        this.#openDocumentIds[
          Math.min(index, this.#openDocumentIds.length - 1)
        ];
      if (next) await this.#openDocument(next);
      else this.#showEmptyDocuments();
      (0, this.#$)("document-tabs")
        .querySelector('[aria-selected="true"]')
        ?.focus();
    } else this.#renderDocumentTabs();
  }
  async #showFiles() {
    const loaded = await this.#api("/api/documents");
    loaded.forEach((doc) => this.#documents.set(doc.id, doc));
    this.#updateGenerationAvailability();
    (0, this.#$)("files-list").replaceChildren(
      ...loaded.map((doc) => {
        const entry = this.#button("", "", () =>
          this.#action(async () => {
            (0, this.#$)("files-dialog").close();
            await this.#openDocument(doc.id);
          }),
        );
        entry.append(
          this.#el("span", "", doc.filename),
          this.#el(
            "small",
            "",
            this.#openDocumentIds.includes(doc.id)
              ? "Open"
              : doc.page_count
                ? `${doc.page_count} pages`
                : "Saved",
          ),
        );
        return entry;
      }),
    );
    if (!loaded.length)
      (0, this.#$)("files-list").append(
        this.#el(
          "p",
          "field-note",
          "No saved files. Use Add files to upload a document.",
        ),
      );
    (0, this.#$)("files-dialog").showModal();
  }
  #renderSetTabs() {
    (0, this.#$)("set-tabs").replaceChildren(
      ...[...this.#sets.values()].map((record) => {
        const wrapper = this.#closableTab(
          record.title,
          record.id === this.#activeSetId,
          () => this.#action(() => this.#openSet(record.id)),
          () => this.#action(() => this.#closeSet(record.id)),
          !record.saved,
        );
        wrapper
          .querySelector('[role="tab"]')
          .setAttribute("aria-controls", "practice-content");
        return wrapper;
      }),
    );
    (0, this.#$)("set-tabs")
      .querySelector('[aria-selected="true"]')
      ?.closest(".closable-tab")
      .scrollIntoView({
        block: "nearest",
        inline: "nearest",
      });
    this.#preference(
      "open-study-sets",
      JSON.stringify(
        [...this.#sets.values()]
          .filter((record) => record.saved)
          .map((record) => record.id),
      ),
    );
    this.#preference("active-study-set", this.#activeSetId || "");
  }
  async #removeSetTab(id) {
    const ids = [...this.#sets.keys()],
      index = ids.indexOf(id);
    if (index < 0) return;
    this.#sets.delete(id);
    if (this.#activeSetId === id) {
      ++this.#setEpoch;
      this.#activeSetId = null;
      const next = [...this.#sets.keys()][Math.min(index, this.#sets.size - 1)];
      if (next) await this.#openSet(next);
      else this.#renderPractice();
      this.#renderSetTabs();
      (0, this.#$)("set-tabs").querySelector('[aria-selected="true"]')?.focus();
    } else this.#renderSetTabs();
  }
  async #closeSet(id) {
    const record = this.#sets.get(id);
    if (!record) return;
    if (!record.saved) {
      const dialog = (0, this.#$)("close-set-dialog");
      dialog.returnValue = "";
      (0, this.#$)("close-set-message").textContent =
        `“${record.title}” has not been saved.`;
      dialog.showModal();
      const choice = await new Promise((resolve) =>
        dialog.addEventListener("close", () => resolve(dialog.returnValue), {
          once: true,
        }),
      );
      if (choice === "save") {
        this.#openSaveDialog(id, true);
        return;
      }
      if (choice !== "discard") return;
    }
    await this.#removeSetTab(id);
  }
  #openSaveDialog(id, closeAfterSave = false) {
    const record = this.#sets.get(id);
    if (!record?.data) return;
    this.#saveIntent = {
      id,
      closeAfterSave,
      cancelled: false,
    };
    (0, this.#$)("set-name").value = record.title;
    (0, this.#$)("save-error").hidden = true;
    (0, this.#$)("confirm-save").textContent = closeAfterSave
      ? "Save and close"
      : "Save";
    (0, this.#$)("save-dialog").showModal();
  }
  #sourceOptions(result) {
    return {
      editable: false,
      onSource: (ref) =>
        this.#action(() => {
          const id = ref.document_id || result.document.id;
          if (!this.#documents.has(id) && id === result.document.id)
            this.#documents.set(id, result.document);
          this.#updateGenerationAvailability();
          return this.#openDocument(id, ref.page, ref);
        }),
      sourceUrl: (ref) =>
        `${this.#fileUrl(ref.document_id || result.document.id)}#page=${ref.page}`,
      sourceLabel: (ref) => `Source · page ${ref.page}`,
    };
  }
  #renderAnswer(container, item, result) {
    const options = this.#sourceOptions(result);
    MathPDF.renderBlocks(container, item.answer, options);
    if (item.source) container.append(MathPDF.citation(item.source, options));
    for (const block of MathPDF.variantBlocks(item)) {
      container.append(this.#el("p", "text-block", block.change));
      container.append(this.#el("p", "field-note", "Original source formula"));
      container.append(
        MathPDF.mathBlock(
          {
            ...block,
            latex: block.original_latex,
          },
          options,
        ),
      );
    }
  }
  #fitFormulas(root) {
    for (const output of root.querySelectorAll(".math-output")) {
      output.style.fontSize = "";
      if (output.clientWidth && output.scrollWidth > output.clientWidth + 1) {
        const base = parseFloat(getComputedStyle(output).fontSize);
        output.style.fontSize = `${base * Math.max(0.65, output.clientWidth / output.scrollWidth) * 0.98}px`;
      }
    }
  }
  #selectItem(index) {
    const record = this.#sets.get(this.#activeSetId);
    if (!record?.data) return;
    if (index < 0 || index >= record.data.items.length) return;
    record.itemIndex = index;
    record.flipped = false;
    record.reviewBrowse = true;
    this.#renderPractice();
  }
  #renderPractice() {
    this.#practiceObserver?.disconnect();
    const record = this.#sets.get(this.#activeSetId),
      result = record?.data;
    this.#renderPracticeToolbar(record, result);
    if (!result?.items.length) {
      (0, this.#$)("practice-content").append(
        this.#el(
          "p",
          "empty-state",
          result
            ? "No study items were generated. Try different source pages."
            : this.#generationActive
              ? "Your study set will appear here when it is ready."
              : "Generate a study set to start practicing.",
        ),
      );
      return;
    }
    record.itemIndex = Math.min(record.itemIndex || 0, result.items.length - 1);
    const itemLabel = result.mode === "flashcards" ? "Card" : "Problem";
    (0, this.#$)("item-tabs").replaceChildren(
      ...result.items.map((item, index) =>
        this.#makeTab(
          `${itemLabel} ${index + 1}`,
          index === record.itemIndex,
          () => this.#selectItem(index),
        ),
      ),
    );
    const item = result.items[record.itemIndex];
    this.#renderPracticeItem(record, result, item);
    this.#practiceObserver = new ResizeObserver(() =>
      this.#fitFormulas((0, this.#$)("practice-content")),
    );
    this.#practiceObserver.observe((0, this.#$)("practice-content"));
    document.fonts.ready.then(() =>
      this.#fitFormulas((0, this.#$)("practice-content")),
    );
  }
  async #openSet(id) {
    const record = this.#sets.get(id);
    if (!record) return;
    this.#activeSetId = id;
    const epoch = ++this.#setEpoch;
    this.#renderSetTabs();
    if (!record.data) {
      (0, this.#$)("practice-content").replaceChildren(
        this.#el("p", "empty-state", "Loading study set…"),
      );
      record.data = await this.#api(
        `/api/study-sets/${encodeURIComponent(id)}`,
      );
    }
    if (epoch !== this.#setEpoch) return;
    record.title = record.data.title;
    this.#renderPractice();
  }
  async #uploadFiles(files) {
    if (!files.length) return;
    const ids = [];
    for (const file of files) {
      if (file.size > 25 * 1024 * 1024) {
        this.#message(`${file.name} exceeds the 25 MB upload limit.`, true);
        continue;
      }
      const id = `local-${crypto.randomUUID()}`;
      ids.push(id);
      this.#pendingUploads.set(id, {
        filename: file.name,
        file,
        controller: null,
        error: null,
      });
      this.#openDocumentIds.push(id);
    }
    if (ids.length) await this.#openDocument(ids[ids.length - 1]);
    for (const id of ids) await this.#saveUpload(id);
  }
  #saveUpload(id) {
    const pending = this.#pendingUploads.get(id);
    if (!pending) return Promise.resolve();
    if (pending.promise) return pending.promise;
    pending.promise = this.#performUpload(id, pending).finally(() => {
      pending.promise = null;
    });
    return pending.promise;
  }
  async #performUpload(id, pending) {
    pending.error = null;
    pending.controller = new AbortController();
    this.#renderUploadState(id);
    const body = new FormData();
    body.append("file", pending.file);
    try {
      const doc = await this.#api("/api/documents", {
        method: "POST",
        body,
        signal: pending.controller.signal,
      });
      this.#documents.set(doc.id, doc);
      this.#updateGenerationAvailability();
      if (!this.#pendingUploads.has(id)) return;
      pending.savedId = doc.id;
      const selected = this.#activeDocumentId === id;
      this.#openDocumentIds = this.#openDocumentIds
        .filter((openId) => openId !== doc.id)
        .map((openId) => (openId === id ? doc.id : openId));
      this.#pendingUploads.delete(id);
      this.#views.get(id)?.remove();
      this.#views.delete(id);
      if (selected) await this.#openDocument(doc.id);
      else this.#renderDocumentTabs();
      if ((0, this.#$)("generation-dialog").open) {
        this.#updateSourceChoices();
        this.#renderContextChoices();
        this.#updateGenerationSummary();
      }
      this.#message(`${doc.filename} saved to server.`);
    } catch (error) {
      if (!this.#pendingUploads.has(id) || error.name === "AbortError") return;
      pending.error = error.message;
      this.#renderUploadState(id);
      this.#message(`${pending.filename}: ${error.message}`, true);
    } finally {
      pending.controller = null;
    }
  }
  #sourceDocument() {
    return this.#documents.get((0, this.#$)("source-document").value);
  }
  #updateGenerationAvailability() {
    const hasPdf = [...this.#documents.values()].some((doc) => doc.page_count);
    (0, this.#$)("open-generation").disabled =
      this.#generationActive || !hasPdf;
    (0, this.#$)("open-generation").title = hasPdf
      ? ""
      : "Upload a PDF to generate study material.";
  }
  #updateSourceChoices() {
    const selected = (0, this.#$)("source-document").value;
    (0, this.#$)("source-document").replaceChildren(
      ...[...this.#documents.values()]
        .filter((doc) => doc.page_count)
        .map((doc) => new Option(doc.filename, doc.id)),
    );
    if (this.#documents.get(selected)?.page_count)
      (0, this.#$)("source-document").value = selected;
  }
  #sourceChanged() {
    const doc = this.#sourceDocument();
    if (!doc) return;
    const page = this.#readState(doc.id).page;
    (0, this.#$)("source-from").max = doc.page_count;
    (0, this.#$)("source-to").max = doc.page_count;
    (0, this.#$)("source-from").value = page;
    (0, this.#$)("source-to").value = page;
    this.#renderContextChoices();
    this.#updateRangeDisabled();
    this.#updateGenerationSummary();
  }
  #updateRangeDisabled() {
    const all = (0, this.#$)("source-scope").value === "all";
    (0, this.#$)("source-from").disabled = all;
    (0, this.#$)("source-to").disabled = all;
  }
  #rangePages(doc, scope, start, end) {
    if (scope === "all") return null;
    const from = Number(start),
      to = Number(end);
    if (
      !Number.isInteger(from) ||
      !Number.isInteger(to) ||
      from < 1 ||
      to < from ||
      to > doc.page_count
    ) {
      throw new Error(
        `${doc.filename}: choose a range from 1 to ${doc.page_count}, with the end at or after the start.`,
      );
    }
    return Array.from(
      {
        length: to - from + 1,
      },
      (_, index) => from + index,
    );
  }
  #selectionRequest() {
    const source = this.#sourceDocument();
    if (!source) throw new Error("Add a PDF and choose it as the source.");
    const pages = this.#rangePages(
      source,
      (0, this.#$)("source-scope").value,
      (0, this.#$)("source-from").value,
      (0, this.#$)("source-to").value,
    );
    const context = [];
    let totalPages = pages?.length || source.page_count;
    for (const [id, choice] of this.#contextChoices) {
      if (!choice.enabled || id === source.id) continue;
      const doc = this.#documents.get(id);
      if (!doc) continue;
      const contextPages = doc.page_count
        ? this.#rangePages(doc, choice.scope, choice.from, choice.to)
        : null;
      totalPages += doc.page_count ? contextPages?.length || doc.page_count : 0;
      context.push({
        document_id: id,
        pages: contextPages,
      });
    }
    if (context.length > 6)
      throw new Error("Attach up to 6 context files per request.");
    if (totalPages > 100)
      throw new Error(
        "Select up to 100 PDF pages across the source and context files.",
      );
    const count = Number((0, this.#$)("count").value),
      maximum = this.#config?.max_items || Number((0, this.#$)("count").max);
    if (!Number.isInteger(count) || count < 1 || count > maximum)
      throw new Error(`Choose between 1 and ${maximum} items.`);
    return {
      document_id: source.id,
      pages,
      context,
      comment: (0, this.#$)("context-comment").value.trim(),
      mode: (0, this.#$)("mode").value,
      count,
      difficulty: Number(
        document.querySelector("input[name=difficulty]:checked").value,
      ),
    };
  }
  #updateGenerationSummary() {
    try {
      const selection = this.#selectionRequest();
      const doc = this.#documents.get(selection.document_id);
      const count = selection.pages?.length || doc.page_count;
      (0, this.#$)("generation-summary").textContent =
        `${selection.count} ${selection.mode === "flashcards" ? "flashcards" : "problems (Beta)"} · Level ${selection.difficulty} · ${count} source ${count === 1 ? "page" : "pages"} · ${selection.context.length} context ${selection.context.length === 1 ? "file" : "files"}`;
      (0, this.#$)("generation-summary").className = "selection-summary";
    } catch (error) {
      (0, this.#$)("generation-summary").textContent = error.message;
      (0, this.#$)("generation-summary").className = "selection-summary error";
    }
  }
  #renderContextChoices() {
    const candidates = [...this.#documents.values()].filter(
      (doc) => doc.id !== (0, this.#$)("source-document").value,
    );
    if (!candidates.length) {
      (0, this.#$)("context-files").replaceChildren(
        this.#el(
          "p",
          "field-note",
          "No additional files. Add PDFs, text, Markdown, or images.",
        ),
      );
      return;
    }
    const rows = candidates.map((doc) => this.#renderContextChoice(doc));
    (0, this.#$)("context-files").replaceChildren(...rows);
  }
  #openGeneration() {
    dispatchEvent(new Event("mathpdf-allowance-changed"));
    this.#updateSourceChoices();
    if (this.#documents.get(this.#activeDocumentId)?.page_count)
      (0, this.#$)("source-document").value = this.#activeDocumentId;
    if (!this.#sourceDocument()) {
      this.#message("Upload a PDF to generate study material.");
      return;
    }
    this.#sourceChanged();
    (0, this.#$)("generation-error").hidden = true;
    (0, this.#$)("generation-dialog").showModal();
  }
  async #generate(event) {
    event.preventDefault();
    if (this.#generationActive || this.#generationPreparing) return;
    const request = await this.#prepareGeneration();
    if (!request) return;
    const { GenerationFlow } = await import("/static/generation-flow.js");
    this.#lastGenerationSelection = request;
    this.#generationActive = true;
    const flow = new GenerationFlow({
      api: this.#api.bind(this),
      ui: this.#$,
      timeout: ((this.#config.generation_timeout_seconds || 150) + 30) * 1000,
      message: this.#message.bind(this),
      accept: this.#acceptGeneration.bind(this),
      limit: this.#showGenerationLimit.bind(this),
      finish: this.#finishGeneration.bind(this),
    });
    this.#generationController = flow.controller;
    if (!this.#sets.get(this.#activeSetId)?.data) this.#renderPractice();
    await flow.run(request);
  }
  async #prepareGeneration() {
    let request;
    try {
      request = this.#selectionRequest();
    } catch (error) {
      this.#$("generation-error").textContent = error.message;
      this.#$("generation-error").hidden = false;
      return null;
    }
    this.#generationPreparing = true;
    this.#$("generate").disabled = true;
    try {
      return await this.#notes.prepare(request);
    } finally {
      this.#generationPreparing = false;
      this.#$("generate").disabled = false;
    }
  }
  async #acceptGeneration(data) {
    this.#sets.set(data.id, {
      id: data.id,
      title: data.title,
      data,
      saved: false,
      itemIndex: 0,
      flipped: false,
    });
    await this.#openSet(data.id);
    this.#message(
      `Created ${data.items.length} ${data.mode === "flashcards" ? "flashcards" : "problems"}.`,
    );
  }
  async #showGenerationLimit(error) {
    const { createGenerationLimitDialog } =
      await import("/static/allowance-ui.js");
    this.#limitDialog ??= createGenerationLimitDialog({
      onAdjust: () => {
        this.#$("generation-dialog").showModal();
        this.#$("count").focus();
      },
    });
    this.#limitDialog.show(error);
  }
  #finishGeneration() {
    this.#generationController = null;
    this.#generationActive = false;
    this.#updateGenerationAvailability();
    this.#$("open-generation").textContent = "Generate";
    if (!this.#sets.get(this.#activeSetId)?.data) this.#renderPractice();
  }
  async #persistSet(record, title = record.title) {
    if (!record.data)
      throw new Error("This study set has not finished loading.");
    const result = await this.#api("/api/study-sets", {
      method: "POST",
      body: JSON.stringify({
        ...record.data,
        title: title.trim(),
      }),
    });
    record.data = result;
    record.title = result.title;
    record.saved = true;
    this.#renderSetTabs();
    if (record.id === this.#activeSetId) this.#renderPractice();
  }
  async #saveSet(event) {
    event.preventDefault();
    const intent = this.#saveIntent,
      record = this.#sets.get(intent?.id);
    if (!record?.data) return;
    (0, this.#$)("confirm-save").disabled = true;
    try {
      await this.#persistSet(record, (0, this.#$)("set-name").value);
      const close = intent.closeAfterSave && !intent.cancelled;
      if (this.#saveIntent === intent && (0, this.#$)("save-dialog").open)
        (0, this.#$)("save-dialog").close();
      if (close) await this.#removeSetTab(record.id);
      else {
        this.#renderSetTabs();
        if (record.id === this.#activeSetId) this.#renderPractice();
      }
      this.#message("Study set saved.");
    } catch (error) {
      if (this.#saveIntent === intent && (0, this.#$)("save-dialog").open) {
        (0, this.#$)("save-error").hidden = false;
        (0, this.#$)("save-error").textContent = error.message;
      } else this.#message(error.message, true);
    } finally {
      (0, this.#$)("confirm-save").disabled = false;
    }
  }
  async #exportSet() {
    const record = this.#sets.get(this.#activeSetId);
    if (!record?.data) return;
    (0, this.#$)("export-set").disabled = true;
    (0, this.#$)("export-set").textContent = "Exporting…";
    this.#message("Formatting your PDF…", false, 0);
    try {
      const response = await MathPDFSession.request("/api/study/export.pdf", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(record.data),
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(
          typeof error.detail === "string"
            ? error.detail
            : "This set could not be exported.",
        );
      }
      const url = URL.createObjectURL(await response.blob());
      const link = this.#el("a");
      link.href = url;
      link.download = `${record.title.replaceAll("/", "-")}.pdf`;
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
      this.#message("PDF ready.");
    } finally {
      (0, this.#$)("export-set").disabled = !this.#sets.get(this.#activeSetId)
        ?.data?.items.length;
      (0, this.#$)("export-set").textContent = "Download";
    }
  }
  async #showSaved() {
    (0, this.#$)("saved-list").replaceChildren(
      this.#el("p", "field-note", "Loading saved sets…"),
    );
    (0, this.#$)("saved-dialog").showModal();
    const saved = await this.#api("/api/study-sets");
    (0, this.#$)("saved-list").replaceChildren(
      ...saved.map((meta) => {
        const entry = this.#button("", "", () =>
          this.#action(async () => {
            if (!this.#sets.has(meta.id))
              this.#sets.set(meta.id, {
                ...meta,
                saved: true,
                data: null,
                itemIndex: 0,
              });
            (0, this.#$)("saved-dialog").close();
            await this.#openSet(meta.id);
          }),
        );
        entry.append(
          this.#el("span", "", meta.title),
          this.#el(
            "small",
            "",
            `${meta.item_count} ${meta.mode === "flashcards" ? "cards" : "problems"}`,
          ),
        );
        return entry;
      }),
    );
    if (!saved.length)
      (0, this.#$)("saved-list").append(
        this.#el("p", "field-note", "No saved study sets yet."),
      );
  }
  #notifyPdfViewport(settled = false) {
    this.#viewportSettled ||= settled;
    cancelAnimationFrame(this.#viewportNotice);
    this.#viewportNotice = requestAnimationFrame(() => {
      this.#views
        .get(this.#activeDocumentId)
        ?.querySelector("iframe")
        ?.contentWindow.postMessage(
          {
            type: "pdf-viewport",
            settled: this.#viewportSettled,
          },
          location.origin,
        );
      this.#viewportSettled = false;
    });
  }
  #chooseFiles() {
    ((0, this.#$)("generation-dialog").open
      ? (0, this.#$)("generation-dialog")
      : document.body
    ).append((0, this.#$)("file-input"));
    (0, this.#$)("file-input").click();
  }
  #pendingWork() {
    return [
      ...(this.#notes?.dirtyDocuments() || []).map(
        (id) => `${this.#documents.get(id)?.filename || "PDF"} · Unsaved notes`,
      ),
      ...[...this.#pendingUploads.values()].map(
        (file) => `${file.filename} · Not uploaded`,
      ),
      ...[...this.#sets.values()]
        .filter((record) => !record.saved)
        .map((record) => `${record.title} · Unsaved study set`),
      ...(this.#generationActive || this.#generationPreparing
        ? ["Study generation in progress"]
        : []),
    ];
  }
  async #savePendingWork() {
    if (this.#generationActive || this.#generationPreparing)
      throw new Error(
        "Wait for generation to finish or cancel it, then save and leave.",
      );
    for (const id of [...this.#pendingUploads.keys()]) {
      await this.#saveUpload(id);
      if (this.#pendingUploads.has(id))
        throw new Error(
          this.#pendingUploads.get(id).error ||
            "The file has not finished uploading.",
        );
    }
    await this.#notes.saveAll();
    for (const record of this.#sets.values())
      if (!record.saved) await this.#persistSet(record);
  }
  async #renameActive(kind) {
    const record =
      kind === "documents"
        ? this.#documents.get(this.#activeDocumentId)
        : this.#sets.get(this.#activeSetId);
    if (!record) return;
    this.#nameDialog ??= (
      await import("/static/rename-ui.js")
    ).createRenameDialog();
    const previous = kind === "documents" ? record.filename : record.title;
    this.#nameDialog.open({
      name: previous,
      kind,
      save: async (name) => {
        if (kind === "study-sets" && !record.saved) {
          name = name.trim();
          if (!name) throw new Error("Enter a study set name.");
          record.title = record.data.title = name;
        } else {
          const updated = await this.#api(
            `/api/library/items/${kind}/${record.id}/name`,
            {
              method: "PATCH",
              body: JSON.stringify({
                name,
                expected_name: previous,
              }),
            },
          );
          if (kind === "documents") {
            this.#documents.set(updated.id, updated);
            const frame = this.#views.get(updated.id)?.querySelector("iframe");
            if (frame) frame.title = updated.filename;
          } else {
            record.title = updated.title;
            record.data = updated;
          }
        }
        this.#renderDocumentTabs();
        this.#updateDocumentToolbar();
        this.#renderSetTabs();
        this.#renderPractice();
        this.#message("Name saved.");
      },
    });
  }
  #bindWindowMessage() {
    window.addEventListener("message", (event) =>
      this.#receivePdfMessage(event),
    );
  }
  #bindAddFilesClick() {
    (0, this.#$)("add-files").addEventListener(
      "click",
      this.#chooseFiles.bind(this),
    );
  }
  #bindUploadPdfClick() {
    (0, this.#$)("upload-pdf").addEventListener(
      "click",
      this.#chooseFiles.bind(this),
    );
  }
  #bindOpenFilesClick() {
    (0, this.#$)("open-files").addEventListener("click", () =>
      this.#action(this.#showFiles.bind(this)),
    );
  }
  #bindAddContextClick() {
    (0, this.#$)("add-context").addEventListener(
      "click",
      this.#chooseFiles.bind(this),
    );
  }
  #bindFileInputChange() {
    (0, this.#$)("file-input").addEventListener("change", () => {
      const files = [...(0, this.#$)("file-input").files];
      (0, this.#$)("file-input").value = "";
      this.#action(() => this.#uploadFiles(files));
    });
  }
  #bindPageFormSubmit() {
    (0, this.#$)("page-form").addEventListener("submit", (event) => {
      event.preventDefault();
      this.#action(() => this.#jumpPage(Number((0, this.#$)("page").value)));
      (0, this.#$)("page").blur();
    });
  }
  #bindPreviousPageClick() {
    (0, this.#$)("previous-page").addEventListener("click", () =>
      this.#action(() =>
        this.#jumpPage(this.#readState(this.#activeDocumentId).page - 1),
      ),
    );
  }
  #bindNextPageClick() {
    (0, this.#$)("next-page").addEventListener("click", () =>
      this.#action(() =>
        this.#jumpPage(this.#readState(this.#activeDocumentId).page + 1),
      ),
    );
  }
  #bindZoomChange() {
    (0, this.#$)("zoom").addEventListener("change", () => {
      this.#readState(this.#activeDocumentId).zoom = (0, this.#$)("zoom").value;
      this.#preference(
        `reading-${this.#activeDocumentId}`,
        JSON.stringify(this.#readState(this.#activeDocumentId)),
      );
      this.#views
        .get(this.#activeDocumentId)
        ?.querySelector("iframe")
        ?.contentWindow.postMessage(
          {
            type: "pdf-zoom",
            zoom: (0, this.#$)("zoom").value,
          },
          location.origin,
        );
    });
  }
  #bindOpenGenerationClick() {
    (0, this.#$)("open-generation").addEventListener("click", () =>
      this.#action(this.#openGeneration.bind(this)),
    );
  }
  #bindSourceDocumentChange() {
    (0, this.#$)("source-document").addEventListener(
      "change",
      this.#sourceChanged.bind(this),
    );
  }
  #bindSourceScopeChange() {
    (0, this.#$)("source-scope").addEventListener("change", () => {
      this.#updateRangeDisabled();
      this.#updateGenerationSummary();
    });
  }
  #bindControlsInput() {
    for (const input of [
      (0, this.#$)("source-from"),
      (0, this.#$)("source-to"),
      (0, this.#$)("mode"),
      (0, this.#$)("count"),
    ])
      input.addEventListener("input", this.#updateGenerationSummary.bind(this));
  }
  #bindInputNameDifficultyChange() {
    for (const input of document.querySelectorAll("input[name=difficulty]"))
      input.addEventListener("change", () => {
        (0, this.#$)("difficulty-description").textContent =
          `${this.#difficultyDescriptions[Number(input.value) - 1]} Items become harder within this level.`;
        this.#updateGenerationSummary();
      });
  }
  #bindGenerateFormSubmit() {
    (0, this.#$)("generate-form").addEventListener("submit", (event) =>
      this.#action(() => this.#generate(event)),
    );
  }
  #bindCancelGenerationClick() {
    (0, this.#$)("cancel-generation").addEventListener("click", () =>
      this.#generationController?.abort(),
    );
  }
  #bindSaveSetClick() {
    (0, this.#$)("save-set").addEventListener("click", () =>
      this.#openSaveDialog(this.#activeSetId),
    );
  }
  #bindSaveDialogCancel() {
    (0, this.#$)("save-dialog").addEventListener("cancel", () => {
      if (this.#saveIntent) this.#saveIntent.cancelled = true;
    });
  }
  #bindSaveFormSubmit() {
    (0, this.#$)("save-form").addEventListener(
      "submit",
      this.#saveSet.bind(this),
    );
  }
  #bindExportSetClick() {
    (0, this.#$)("export-set").addEventListener("click", () =>
      this.#action(this.#exportSet.bind(this)),
    );
  }
  #bindOpenSavedClick() {
    (0, this.#$)("open-saved").addEventListener("click", () =>
      this.#action(this.#showSaved.bind(this)),
    );
  }
  #bindCloseDialogClick() {
    document.querySelectorAll(".close-dialog").forEach((control) =>
      control.addEventListener("click", () => {
        if (control.dataset.dialog === "save-dialog" && this.#saveIntent)
          this.#saveIntent.cancelled = true;
        (0, this.#$)(control.dataset.dialog).close();
      }),
    );
  }
  #registerDiagnosticContext() {
    MathPDFSession.setContextProvider?.(async () => ({
      workspace: {
        active_document: this.#documents.get(this.#activeDocumentId) || null,
        reading: this.#activeDocumentId
          ? this.#readState(this.#activeDocumentId)
          : null,
        study_set: this.#sets.get(this.#activeSetId)?.data || null,
        item_index: this.#sets.get(this.#activeSetId)?.itemIndex ?? null,
        generation_selection: this.#lastGenerationSelection || null,
        generation_running: this.#generationActive,
        unsaved_notes: (await this.#notes?.diagnosticContext?.()) || [],
      },
    }));
  }
  #bindRenameFileClick() {
    (0, this.#$)("rename-file").addEventListener("click", () =>
      this.#action(() => this.#renameActive("documents")),
    );
  }
  #bindRenameSetClick() {
    (0, this.#$)("rename-set").addEventListener("click", () =>
      this.#action(() => this.#renameActive("study-sets")),
    );
  }
  #renderContextChoice(doc) {
    const __owner = this;
    if (!__owner.#contextChoices.has(doc.id))
      __owner.#contextChoices.set(doc.id, {
        enabled: false,
        scope: "all",
        from: 1,
        to: doc.page_count || 1,
      });
    const choice = __owner.#contextChoices.get(doc.id),
      row = __owner.#el("div", "context-file");
    const label = __owner.#el("label", "context-check"),
      checkbox = __owner.#el("input");
    checkbox.type = "checkbox";
    checkbox.checked = choice.enabled;
    label.append(checkbox, __owner.#el("span", "", doc.filename));
    row.append(label);
    const rangeInputs = [];
    function refreshDisabled() {
      for (const input of rangeInputs)
        input.disabled =
          !choice.enabled ||
          (input.type === "number" && choice.scope === "all");
    }
    checkbox.addEventListener("change", () => {
      choice.enabled = checkbox.checked;
      refreshDisabled();
      __owner.#updateGenerationSummary();
    });
    __owner.#renderContextRange(doc, choice, row, rangeInputs, refreshDisabled);
    return row;
  }
  async #initializeWorkspace() {
    const user = await MathPDFSession.ready;
    this.#wireFlashcard = (
      await import("/static/card-interaction.js")
    ).wireFlashcard;
    const { StudyItemsView } = await import("/static/workspace-study-items.js");
    this.#studyItemsView = new StudyItemsView({
      makeElement: (...args) => this.#el(...args),
      makeButton: (...args) => this.#button(...args),
      renderAnswer: (...args) => this.#renderAnswer(...args),
      sourceOptions: (result) => this.#sourceOptions(result),
      selectItem: (index) => this.#selectItem(index),
      reviewUI: () => this.#reviewUI,
      wireFlashcard: this.#wireFlashcard,
    });
    this.#preferencePrefix = `mathpdf-${user.id}-`;
    await this.#installReviews(user);
    await this.#installLayout();
    await this.#installAnnotations();
    await this.#installLeaveGuard();
    const [loadedDocuments, configuration, saved] = await Promise.all([
      this.#api("/api/documents"),
      this.#api("/api/generation/config"),
      this.#api("/api/study-sets"),
    ]);
    this.#config = configuration;
    (0, this.#$)("count").max = this.#config.max_items;
    loadedDocuments.forEach((doc) => this.#documents.set(doc.id, doc));
    this.#updateGenerationAvailability();
    const [selection] = await this.#restoreDocumentTabs();
    await this.#restoreStudyTabs(saved, selection);
    this.#initializing = false;
    if (!this.#config.configured)
      this.#message(
        "Generation is currently unavailable. You can still read files and open saved sets.",
        true,
        10000,
      );
  }
  #bindRenameActions() {
    this.#nameDialog = undefined;
    this.#bindRenameFileClick();
    this.#bindRenameSetClick();
  }
  #bindGenerationActions() {
    this.#difficultyDescriptions = [
      "Recall core facts and meanings.",
      "Explain conditions and apply one idea.",
      "Apply concepts with a few reasoning steps.",
      "Connect ideas and justify careful distinctions.",
      "Explore deeper reasoning, proofs and edge cases.",
    ];
    this.#bindInputNameDifficultyChange();
    this.#bindGenerateFormSubmit();
    this.#bindCancelGenerationClick();
    this.#bindSaveSetClick();
    this.#bindSaveDialogCancel();
    this.#bindSaveFormSubmit();
    this.#bindExportSetClick();
    this.#bindOpenSavedClick();
    this.#bindCloseDialogClick();
    this.#action(async () => this.#initializeWorkspace());
    this.#registerDiagnosticContext();
    MathPDFSession.setUIContextProvider?.(() => ({
      document_id: this.#activeDocumentId,
      study_set_id: this.#activeSetId,
      file_name: this.#documents.get(this.#activeDocumentId)?.filename,
      page: this.#activeDocumentId
        ? this.#readState(this.#activeDocumentId).page
        : undefined,
      item_index: this.#sets.get(this.#activeSetId)?.itemIndex,
    }));
  }
  #bindDocumentActions() {
    this.#bindWindowMessage();
    for (const container of [
      (0, this.#$)("document-tabs"),
      (0, this.#$)("set-tabs"),
      (0, this.#$)("item-tabs"),
    ])
      this.#wireTabs(container);
    this.#bindAddFilesClick();
    this.#bindUploadPdfClick();
    this.#bindOpenFilesClick();
    this.#bindAddContextClick();
    this.#bindFileInputChange();
    this.#bindPageFormSubmit();
    this.#bindPreviousPageClick();
    this.#bindNextPageClick();
    this.#bindZoomChange();
    this.#bindOpenGenerationClick();
    this.#bindSourceDocumentChange();
    this.#bindSourceScopeChange();
    this.#bindControlsInput();
  }
  #initializeWorkspaceState() {
    this.#$ = (id) => document.getElementById(id);
    this.#documents = new Map();
    this.#views = new Map();
    this.#reading = new Map();
    this.#sets = new Map();
    this.#contextChoices = new Map();
    this.#pendingUploads = new Map();
    this.#openDocumentIds = [];
    this.#activeDocumentId = undefined;
    this.#activeSetId = undefined;
    this.#config = undefined;
    this.#generationActive = false;
    this.#generationPreparing = false;
    this.#setEpoch = 0;
    this.#saveIntent = undefined;
    this.#notes = undefined;
    this.#generationController = undefined;
    this.#lastGenerationSelection = undefined;
    this.#statusTimer = undefined;
    this.#practiceObserver = undefined;
    this.#viewportNotice = undefined;
    this.#viewportSettled = false;
    this.#layout = undefined;
    this.#initializing = true;
    this.#preferencePrefix = undefined;
    this.#reviewUI = undefined;
    this.#limitDialog = undefined;
    this.#wireFlashcard = undefined;
    this.#studyItemsView = undefined;
  }
  #createDocumentView(doc, id, state) {
    const view = this.#el("div", "document-view");
    view.id = `document-view-${id}`;
    this.#views.set(id, view);
    (0, this.#$)("document-views").append(view);
    this.#renderDocumentContent(view, doc, id, state);
    return [view];
  }
  #renderPracticeToolbar(record, result) {
    (0, this.#$)("practice-content").replaceChildren();
    (0, this.#$)("item-tabs").replaceChildren();
    (0, this.#$)("item-tabs").hidden = !result?.items.length;
    (0, this.#$)("rename-set").disabled = !result?.items.length;
    (0, this.#$)("save-set").disabled =
      !result?.items.length || !!record?.saved;
    (0, this.#$)("save-set").textContent = record?.saved ? "Saved" : "Save";
    (0, this.#$)("export-set").disabled = !result?.items.length;
    const itemWord = result?.mode === "flashcards" ? "card" : "problem";
    (0, this.#$)("set-status").textContent = result
      ? `${record.saved ? "Saved" : "Unsaved"} · ${result.items.length} ${itemWord}${result.items.length === 1 ? "" : "s"} · Level ${result.difficulty ?? 3}${result.mode === "problems" ? " · Beta" : ""}`
      : "Study material";
    (0, this.#$)("set-status").title = result
      ? "Source transcription has not been verified against the PDF."
      : "";
    (0, this.#$)("study-notes").hidden = !result?.notes.length;
    const notes = this.#el("details");
    notes.append(this.#el("summary", "", "Generation notes"));
    notes.append(
      ...(result?.notes || []).map((note) => this.#el("p", "", note)),
    );
    (0, this.#$)("study-notes").replaceChildren(notes);
  }
  async #restoreStudyTabs(saved, selection) {
    let storedSets;
    try {
      storedSets = JSON.parse(this.#preference("open-study-sets"));
    } catch {}
    const savedById = new Map(saved.map((meta) => [meta.id, meta]));
    const openSaved = Array.isArray(storedSets)
      ? [...new Set(storedSets)].filter((id) => savedById.has(id))
      : saved.map((meta) => meta.id);
    const requestedSet = selection.get("set");
    if (savedById.has(requestedSet) && !openSaved.includes(requestedSet))
      openSaved.push(requestedSet);
    for (const id of openSaved)
      this.#sets.set(id, {
        ...savedById.get(id),
        saved: true,
        data: null,
        itemIndex: 0,
      });
    const selectedSet = this.#sets.has(requestedSet)
      ? requestedSet
      : this.#sets.has(this.#preference("active-study-set"))
        ? this.#preference("active-study-set")
        : openSaved[0];
    if (selectedSet) await this.#openSet(selectedSet);
    else {
      this.#renderSetTabs();
      this.#renderPractice();
    }
    if (requestedSet && this.#sets.get(requestedSet)?.data) {
      const source = this.#sets.get(requestedSet).data.document;
      await this.#openDocument(
        source.id,
        this.#preference(`reading-${source.id}`)
          ? this.#readState(source.id).page
          : this.#sets.get(requestedSet).data.pages[0],
      );
    }
  }
  async #restoreDocumentTabs() {
    let storedFiles;
    try {
      storedFiles = JSON.parse(this.#preference("open-files"));
    } catch {}
    this.#openDocumentIds = Array.isArray(storedFiles)
      ? [...new Set(storedFiles.filter((id) => this.#documents.has(id)))]
      : [...this.#documents.keys()];
    const selection = new URLSearchParams(location.search);
    const selectedDocument = selection.get("document");
    if (
      selectedDocument &&
      this.#documents.has(selectedDocument) &&
      !this.#openDocumentIds.includes(selectedDocument)
    )
      this.#openDocumentIds.push(selectedDocument);
    const initial = this.#documents.has(selectedDocument)
      ? selectedDocument
      : this.#openDocumentIds.includes(this.#preference("active-file"))
        ? this.#preference("active-file")
        : this.#openDocumentIds[0];
    if (initial) await this.#openDocument(initial);
    else this.#showEmptyDocuments();
    return [selection];
  }
  async #installLeaveGuard() {
    const { createLeaveGuard } = await import("/static/leave-guard.js");
    const leave = createLeaveGuard({
      pending: this.#pendingWork.bind(this),
      save: this.#savePendingWork.bind(this),
    });
    MathPDFSession.setLeaveGuard(
      () => leave.confirm(),
      () => leave.reset(),
    );
    document.querySelector("a.brand").addEventListener("click", (event) => {
      if (
        event.button !== 0 ||
        event.ctrlKey ||
        event.metaKey ||
        event.shiftKey ||
        event.altKey
      )
        return;
      event.preventDefault();
      this.#action(async () => {
        if (await leave.confirm()) location.assign("/");
      });
    });
  }
  async #installAnnotations() {
    const { createAnnotationToolbar } =
      await import("/static/annotation-toolbar.js");
    this.#notes = createAnnotationToolbar({
      activeDocument: () => this.#documents.get(this.#activeDocumentId),
      documentFor: (id) => this.#documents.get(id),
      frameFor: (id) => this.#views.get(id)?.querySelector("iframe"),
      notifyViewport: this.#notifyPdfViewport.bind(this),
      report: (text) => this.#message(text, true, 10000),
      onChange: () => this.#renderDocumentTabs(),
      onOpenCopy: async (doc) => {
        this.#documents.set(doc.id, doc);
        await this.#openDocument(doc.id);
      },
      onSaved: (previous, doc) => {
        this.#documents.set(doc.id, doc);
        if (previous !== doc.id) {
          const view = this.#views.get(previous);
          this.#views.delete(previous);
          if (view) {
            view.id = `document-view-${doc.id}`;
            view.querySelector("iframe").title = doc.filename;
            this.#views.set(doc.id, view);
          }
          if (!this.#openDocumentIds.includes(doc.id))
            this.#openDocumentIds.splice(
              this.#openDocumentIds.indexOf(previous) + 1,
              0,
              doc.id,
            );
          this.#reading.set(doc.id, {
            ...this.#readState(previous),
          });
          if (this.#activeDocumentId === previous) {
            this.#activeDocumentId = doc.id;
            this.#preference("active-file", doc.id);
          }
        }
        this.#renderDocumentTabs();
        this.#updateDocumentToolbar();
        this.#message("PDF notes saved.");
      },
    });
  }
  async #installLayout() {
    const { createWorkspaceLayout } =
      await import("/static/workspace-layout.js");
    this.#layout = createWorkspaceLayout({
      preference: this.#preference.bind(this),
      onViewport: this.#notifyPdfViewport.bind(this),
    });
  }
  async #installReviews(user) {
    const { createReviewUI } = await import("/static/review-ui.js");
    this.#reviewUI = createReviewUI({
      api: this.#api.bind(this),
      userId: user.id,
      onChange: (record) => {
        if (record.id === this.#activeSetId) this.#renderPractice();
      },
      select: (record, index) => {
        record.itemIndex = index;
        record.flipped = false;
        if (record.id === this.#activeSetId) this.#renderPractice();
      },
      onError: (text) => this.#message(text, true),
    });
  }
  #renderPracticeItem(record, result, item) {
    (0, this.#$("practice-content")).append(
      this.#studyItemsView.render(record, result, item),
    );
  }
  #renderContextRange(doc, choice, row, rangeInputs, refreshDisabled) {
    if (doc.page_count) {
      const controls = this.#el("div", "range-controls");
      const scopeLabel = this.#el("label", "", "Pages"),
        scope = this.#el("select");
      scope.append(
        new Option("Entire PDF", "all"),
        new Option("Page range", "range"),
      );
      scope.value = choice.scope;
      scope.setAttribute("aria-label", `Pages for ${doc.filename}`);
      scopeLabel.append(scope);
      controls.append(scopeLabel);
      rangeInputs.push(scope);
      scope.addEventListener("change", () => {
        choice.scope = scope.value;
        refreshDisabled();
        this.#updateGenerationSummary();
      });
      for (const [key, name] of [
        ["from", "From"],
        ["to", "To"],
      ]) {
        const inputLabel = this.#el("label", "", name),
          input = this.#el("input");
        input.type = "number";
        input.min = 1;
        input.max = doc.page_count;
        input.value = choice[key];
        input.required = true;
        input.setAttribute("aria-label", `${name} page for ${doc.filename}`);
        inputLabel.append(input);
        controls.append(inputLabel);
        rangeInputs.push(input);
        input.addEventListener("input", () => {
          choice[key] = input.value;
          this.#updateGenerationSummary();
        });
      }
      row.append(controls);
      refreshDisabled();
    } else row.append(this.#el("p", "field-note", "Entire file"));
  }
  #receivePdfMessage(event) {
    const data = event.data;
    if (this.#refreshExpiredSession(event, data)) return;
    if (
      event.origin !== location.origin ||
      !data ||
      !["pdf-page", "pdf-ready"].includes(data.type)
    )
      return;
    const view = this.#views.get(data.documentId),
      doc = this.#documents.get(data.documentId);
    const iframe = view?.querySelector("iframe");
    if (!iframe || event.source !== iframe.contentWindow || !doc) return;
    if (data.type === "pdf-ready") {
      iframe.dataset.ready = "true";
      if (iframe.pendingNavigation) {
        iframe.contentWindow.postMessage(
          iframe.pendingNavigation,
          location.origin,
        );
        delete iframe.pendingNavigation;
      }
      return;
    }
    if (
      !Number.isInteger(data.page) ||
      data.page < 1 ||
      data.page > doc.page_count
    )
      return;
    this.#readState(doc.id).page = data.page;
    this.#preference(
      `reading-${doc.id}`,
      JSON.stringify(this.#readState(doc.id)),
    );
    if (
      this.#activeDocumentId === doc.id &&
      document.activeElement !== (0, this.#$)("page")
    )
      this.#updateDocumentToolbar();
  }
  #refreshExpiredSession(event, data) {
    if (
      event.origin === location.origin &&
      data?.type === "session-expired" &&
      [...this.#views.values()].some(
        (view) => event.source === view.querySelector("iframe")?.contentWindow,
      )
    ) {
      this.#action(() => MathPDFSession.api("/api/me"));
      return true;
    }
    return false;
  }
  #renderDocumentContent(view, doc, id, state) {
    if (this.#pendingUploads.has(id)) {
      view.append(this.#el("div", "upload-state"));
    } else if (doc.page_count) {
      const iframe = this.#el("iframe");
      iframe.title = doc.filename;
      iframe.src = `/static/pdf-viewer.html?document=${encodeURIComponent(id)}&page=${state.page}&zoom=${encodeURIComponent(state.zoom)}`;
      iframe.addEventListener("load", () => {
        iframe.contentWindow.postMessage(
          {
            type: "pdf-zoom",
            zoom: state.zoom,
          },
          location.origin,
        );
        iframe.contentWindow.postMessage(
          {
            type: "pdf-viewport",
            settled: true,
          },
          location.origin,
        );
      });
      view.append(iframe);
    } else if (doc.media_type.startsWith("image/")) {
      const image = this.#el("img", "image-preview");
      image.alt = doc.filename;
      image.src = this.#fileUrl(id);
      view.append(image);
    } else {
      const preview = this.#el("pre", "text-preview", "Loading file…");
      view.append(preview);
      MathPDFSession.request(this.#fileUrl(id))
        .then((response) => {
          if (!response.ok) throw new Error("This file could not be loaded.");
          return response.text();
        })
        .then((text) => {
          preview.textContent = text;
        })
        .catch((error) => {
          preview.textContent = error.message;
        });
    }
  }
}
new WorkspaceController();

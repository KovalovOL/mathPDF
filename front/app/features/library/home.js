class LibraryController {
  constructor() {
    this.#home = (id) => document.getElementById(id);
    this.#uploading = false;
    this.#uploadTask = undefined;
    this.#uploadFailure = undefined;
    this.#pendingFiles = [];
    this.#previews = undefined;
    this.#deleteIntent = undefined;
    this.#diagnosticItem = undefined;
    this.#previewModule = import("/static/file-previews.js").catch(() => null);
    this.#bindCancelDeleteClick();
    this.#bindDeleteDialogCancel();
    this.#bindDeleteFormSubmit();
    this.#library = {
      folders: [],
      files: [],
      sets: [],
    };
    this.#currentFolder = null;
    this.#archiveView = false;
    this.#folderIntent = undefined;
    this.#moveIntent = undefined;
    this.#removeFolderIntent = undefined;
    this.#folderIcon =
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7V5h6l2 2h10v13H3Z"/></svg>';
    this.#previewRenderer = undefined;
    this.#bindNewFolderClick();
    this.#bindArchiveViewClick();
    this.#bindFolderFormSubmit();
    this.#bindMoveFormSubmit();
    this.#bindRemoveFolderFormSubmit();
    this.#bindDataCloseClick();
    this.#bindButtonTypeSubmitDisabledCancel();
    addEventListener("popstate", () => {
      this.#readLocation();
      this.#renderLibrary();
    });
    this.#bindDocumentClick();
    this.#bindDocumentKeydown();
    this.#bindUploadFilesClick();
    this.#bindLibraryFileInputChange();
    addEventListener("pagehide", () => this.#previews?.destroy());
    MathPDFSession.ready
      .then(async (user) => this.#initializeLibrary(user))
      .catch(this.#showError.bind(this));
    this.#registerDiagnosticContext();
    this.#nameDialog = undefined;
    MathPDFSession.setUIContextProvider?.(() => this.#diagnosticItem || {});
  }
  #home;
  #uploading;
  #uploadTask;
  #uploadFailure;
  #pendingFiles;
  #previews;
  #deleteIntent;
  #diagnosticItem;
  #previewModule;
  #library;
  #currentFolder;
  #archiveView;
  #folderIntent;
  #moveIntent;
  #removeFolderIntent;
  #folderIcon;
  #previewRenderer;
  #nameDialog;
  #node(tag, className, text) {
    const element = document.createElement(tag);
    element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }
  #fileMetadata(file) {
    const type = file.page_count
      ? `PDF · ${file.page_count} ${file.page_count === 1 ? "page" : "pages"}`
      : file.media_type.startsWith("image/")
        ? "Image"
        : file.media_type === "text/markdown"
          ? "Markdown"
          : "Text";
    const size =
      file.size < 1024 * 1024
        ? `${Math.max(1, Math.round(file.size / 1024))} KB`
        : `${(file.size / 1024 / 1024).toFixed(1)} MB`;
    return `${type} · ${size}`;
  }
  #row(title, metadata, url) {
    const item = this.#node("div", "library-row");
    const link = this.#node("a", "library-item-link");
    link.href = url;
    link.append(
      this.#node("span", "library-item-title", title),
      this.#node("span", "library-item-meta", metadata),
    );
    item.append(link);
    return item;
  }
  #chooseFiles() {
    if (!this.#uploading) {
      if (this.#archiveView) this.#navigateFolder(null);
      (0, this.#home)("library-file-input").click();
    }
  }
  #showDeletion(impact) {
    (0, this.#home)("delete-heading").textContent =
      this.#deleteIntent.kind === "documents"
        ? "Delete file?"
        : "Delete study set?";
    (0, this.#home)("delete-message").textContent =
      `Permanently delete “${impact.title}”? This cannot be undone.`;
    const count = impact.study_sets.length;
    const copies = impact.edited_copies?.length || 0,
      consequences = [];
    if (copies)
      consequences.push(`${copies} edited ${copies === 1 ? "copy" : "copies"}`);
    if (count)
      consequences.push(
        `${count} saved study ${count === 1 ? "set" : "sets"} using ${copies ? "this file or its edited copy" : "this file"} as the main source`,
      );
    (0, this.#home)("delete-warning").textContent = consequences.length
      ? `This will also permanently delete ${consequences.join(" and ")}.`
      : "";
    (0, this.#home)("delete-context").textContent = impact.context_sets.length
      ? `${impact.context_sets.length} saved ${impact.context_sets.length === 1 ? "set used" : "sets used"} this file only as additional context. Those sets will remain; the context attachment will be removed.`
      : "";
  }
  async #confirmDeletion(kind, id) {
    const impact = await MathPDFSession.api(
      `/api/${kind}/${encodeURIComponent(id)}/deletion`,
    );
    this.#deleteIntent = {
      kind,
      id,
      impact,
    };
    this.#showDeletion(impact);
    (0, this.#home)("delete-error").hidden = true;
    (0, this.#home)("confirm-delete").disabled = false;
    (0, this.#home)("delete-dialog").showModal();
  }
  #control(text, className, action, label) {
    const b = this.#node("button", className, text);
    b.type = "button";
    if (label) b.setAttribute("aria-label", label);
    b.addEventListener("click", () =>
      Promise.resolve().then(action).catch(this.#showError.bind(this)),
    );
    return b;
  }
  #jsonWrite(method, data) {
    return {
      method,
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    };
  }
  #folderPath(id) {
    const path = [],
      seen = new Set();
    let f = this.#library.folders.find((f) => f.id === id);
    while (f && !seen.has(f.id)) {
      seen.add(f.id);
      path.unshift(f);
      f = this.#library.folders.find((p) => p.id === f.parent_id);
    }
    return path;
  }
  #locationName(id) {
    return ["Your library", ...this.#folderPath(id).map((f) => f.name)].join(
      " / ",
    );
  }
  #navigateFolder(id, archive = false) {
    this.#currentFolder = id;
    this.#archiveView = archive;
    const url = new URL(location.href);
    url.searchParams.delete("folder");
    url.searchParams.delete("view");
    if (id && !archive) url.searchParams.set("folder", id);
    if (archive) url.searchParams.set("view", "archive");
    history.pushState(null, "", url);
    this.#renderLibrary();
  }
  #readLocation() {
    const query = new URLSearchParams(location.search);
    this.#currentFolder = query.get("folder");
    this.#archiveView = query.get("view") === "archive";
    if (
      this.#currentFolder &&
      !this.#library.folders.some((f) => f.id === this.#currentFolder)
    )
      this.#currentFolder = null;
  }
  #menu(title, actions) {
    const details = this.#node("details", "item-menu"),
      summary = this.#node("summary", "", "⋯");
    summary.setAttribute("aria-label", `Actions for ${title}`);
    const panel = this.#node("div", "item-menu-panel");
    for (const [text, action, danger] of actions)
      panel.append(
        this.#control(
          text,
          danger ? "menu-danger" : "",
          () => {
            details.open = false;
            return action();
          },
          `${text} ${title}`,
        ),
      );
    details.append(summary, panel);
    return details;
  }
  #itemMenu(kind, item, title) {
    const context = (operation) => () => {
      this.#diagnosticItem = {
        ...(kind === "documents"
          ? {
              document_id: item.id,
              file_name: title,
            }
          : {
              study_set_id: item.id,
              document_id: item.document_id,
              file_name: item.document_filename,
            }),
      };
      return operation();
    };
    return this.#menu(
      title,
      [
        ["Rename", () => this.#renameLibraryItem(kind, item, title)],
        ["Move", () => this.#showMove(kind, item.id, title, item.folder_id)],
        [
          item.archived ? "Restore" : "Archive",
          () =>
            this.#organize(kind, item.id, {
              archived: !item.archived,
            }),
        ],
        ["Delete", () => this.#confirmDeletion(kind, item.id), true],
      ].map(([name, operation, danger]) => [name, context(operation), danger]),
    );
  }
  async #organize(kind, id, update) {
    await MathPDFSession.api(
      `/api/library/items/${kind}/${encodeURIComponent(id)}`,
      this.#jsonWrite("PATCH", update),
    );
    await this.#loadLibrary();
  }
  #dragItem(element, kind, id) {
    element.draggable = true;
    element.addEventListener("dragstart", (event) => {
      if (event.target.closest("button,summary")) {
        event.preventDefault();
        return;
      }
      event.dataTransfer.setData(
        "application/x-mathpdf-item",
        JSON.stringify({
          kind,
          id,
        }),
      );
      event.dataTransfer.effectAllowed = "move";
    });
  }
  #dropFolder(element, id) {
    element.addEventListener("dragover", (event) => {
      if (
        [...event.dataTransfer.types].includes("application/x-mathpdf-item")
      ) {
        event.preventDefault();
        element.classList.add("drop-target");
        event.dataTransfer.dropEffect = "move";
      }
    });
    element.addEventListener("dragleave", () =>
      element.classList.remove("drop-target"),
    );
    element.addEventListener("drop", (event) => {
      event.preventDefault();
      element.classList.remove("drop-target");
      try {
        const { kind, id: itemId } = JSON.parse(
          event.dataTransfer.getData("application/x-mathpdf-item"),
        );
        const known =
          kind === "folders"
            ? this.#library.folders
            : kind === "documents"
              ? this.#library.files
              : kind === "study-sets"
                ? this.#library.sets
                : [];
        if (!known.some((item) => item.id === itemId)) return;
        (kind === "folders"
          ? MathPDFSession.api(
              `/api/library/folders/${itemId}`,
              this.#jsonWrite("PATCH", {
                parent_id: id,
              }),
            ).then(this.#loadLibrary.bind(this))
          : this.#organize(kind, itemId, {
              folder_id: id,
            })
        ).catch(this.#showError.bind(this));
      } catch {
        this.#showError(new Error("This item could not be moved."));
      }
    });
  }
  #renderNavigation() {
    (0, this.#home)("new-folder").disabled = false;
    (0, this.#home)("archive-view").disabled = false;
    (0, this.#home)("library-breadcrumbs").hidden =
      !this.#currentFolder && !this.#archiveView;
    (0, this.#home)("archive-view").setAttribute(
      "aria-pressed",
      String(this.#archiveView),
    );
    const archived =
      this.#library.files.filter((f) => f.archived).length +
      this.#library.sets.filter((s) => s.archived).length;
    (0, this.#home)("archive-count").textContent = archived
      ? String(archived)
      : "";
    (0, this.#home)("archive-note").hidden = !this.#archiveView;
    (0, this.#home)("new-folder").hidden = this.#archiveView;
    this.#renderBreadcrumbs();
    this.#renderFolderChildren();
  }
  #renderLibrary() {
    this.#previews?.destroy();
    this.#previews = this.#previewRenderer?.createFilePreviews({
      request: MathPDFSession.request,
      userId: MathPDFSession.user.id,
      onAuthFailure: () => MathPDFSession.api("/api/me").catch(() => {}),
    });
    this.#renderNavigation();
    (0, this.#home)("library-error").hidden = true;
    const visible = (item) =>
      this.#archiveView
        ? item.archived
        : !item.archived && item.folder_id === this.#currentFolder;
    const files = this.#library.files.filter(visible),
      sets = this.#library.sets.filter(visible);
    this.#renderLibraryFiles(files, sets);
    this.#renderLibrarySets(sets);
  }
  async #loadLibrary() {
    const [data, renderer] = await Promise.all([
      MathPDFSession.api("/api/library"),
      this.#previewModule,
    ]);
    this.#library = data;
    this.#previewRenderer = renderer;
    this.#readLocation();
    this.#renderLibrary();
  }
  #showFolder(folder = null) {
    this.#folderIntent = folder;
    (0, this.#home)("folder-heading").textContent = folder
      ? "Rename folder"
      : "New folder";
    (0, this.#home)("confirm-folder").textContent = folder
      ? "Save name"
      : "Create folder";
    (0, this.#home)("folder-name").value = folder?.name || "";
    (0, this.#home)("folder-error").hidden = true;
    (0, this.#home)("folder-dialog").showModal();
    (0, this.#home)("folder-name").focus();
  }
  async #showRemoveFolder(folder) {
    this.#removeFolderIntent = await MathPDFSession.api(
      `/api/library/folders/${folder.id}/deletion`,
    );
    (0, this.#home)("remove-folder-message").textContent =
      `Remove “${this.#removeFolderIntent.name}”? Its ${this.#removeFolderIntent.item_count} items and ${this.#removeFolderIntent.folder_count} subfolders will be kept.`;
    (0, this.#home)("remove-folder-error").hidden = true;
    (0, this.#home)("remove-folder-dialog").showModal();
  }
  #showMove(kind, id, title, folder) {
    this.#moveIntent = {
      kind,
      id,
    };
    (0, this.#home)("move-item-name").textContent = title;
    (0, this.#home)("move-error").hidden = true;
    const descendants = new Set([id]);
    if (kind === "folders") {
      let changed = true;
      while (changed) {
        changed = false;
        for (const f of this.#library.folders)
          if (descendants.has(f.parent_id) && !descendants.has(f.id)) {
            descendants.add(f.id);
            changed = true;
          }
      }
    }
    const choices = [
      {
        id: "",
        name: "Your library",
      },
      ...this.#library.folders
        .filter((f) => kind !== "folders" || !descendants.has(f.id))
        .map((f) => ({
          id: f.id,
          name: this.#locationName(f.id),
        }))
        .sort((a, b) => a.name.localeCompare(b.name)),
    ];
    (0, this.#home)("move-destination").replaceChildren(
      ...choices.map((f) => new Option(f.name, f.id)),
    );
    (0, this.#home)("move-destination").value = folder || "";
    (0, this.#home)("move-dialog").showModal();
  }
  async #submitDialog(event, id, button, errorId, operation) {
    event.preventDefault();
    (0, this.#home)(button).disabled = true;
    (0, this.#home)(errorId).hidden = true;
    try {
      await operation();
      (0, this.#home)(id).close();
      await this.#loadLibrary();
    } catch (error) {
      (0, this.#home)(errorId).textContent = error.message;
      (0, this.#home)(errorId).hidden = false;
    } finally {
      (0, this.#home)(button).disabled = false;
    }
  }
  #showError(error) {
    (0, this.#home)("library-error").textContent = error.message;
    (0, this.#home)("library-error").hidden = false;
  }
  async #uploadFiles() {
    this.#uploading = true;
    (0, this.#home)("upload-files").disabled = true;
    (0, this.#home)("library-error").hidden = true;
    this.#uploadFailure = null;
    (0, this.#home)("upload-status").hidden = false;
    const failures = [],
      targetFolder = this.#archiveView ? null : this.#currentFolder;
    try {
      const [completed] = await this.#uploadPendingFiles(
        targetFolder,
        failures,
      );
      await this.#loadLibrary();
      (0, this.#home)("upload-status").textContent =
        `${completed} ${completed === 1 ? "file" : "files"} uploaded.`;
      if (failures.length) throw new Error(failures.join("\n"));
    } catch (error) {
      this.#uploadFailure = error;
      this.#showError(error);
    } finally {
      this.#uploading = false;
      (0, this.#home)("upload-files").disabled = false;
    }
  }
  async #renameLibraryItem(kind, item, title) {
    this.#nameDialog ??= (
      await import("/static/rename-ui.js")
    ).createRenameDialog();
    this.#nameDialog.open({
      name: title,
      kind,
      save: async (name) => {
        await MathPDFSession.api(
          `/api/library/items/${kind}/${item.id}/name`,
          this.#jsonWrite("PATCH", {
            name,
            expected_name: title,
          }),
        );
        await this.#loadLibrary();
      },
    });
  }
  #bindCancelDeleteClick() {
    (0, this.#home)("cancel-delete").addEventListener("click", () =>
      (0, this.#home)("delete-dialog").close(),
    );
  }
  #bindDeleteDialogCancel() {
    (0, this.#home)("delete-dialog").addEventListener("cancel", (event) => {
      if ((0, this.#home)("confirm-delete").disabled) event.preventDefault();
    });
  }
  #bindDeleteFormSubmit() {
    (0, this.#home)("delete-form").addEventListener("submit", async (event) =>
      this.#submitDeletion(event),
    );
  }
  #bindNewFolderClick() {
    (0, this.#home)("new-folder").addEventListener("click", () =>
      this.#showFolder(),
    );
  }
  #bindArchiveViewClick() {
    (0, this.#home)("archive-view").addEventListener("click", () =>
      this.#navigateFolder(null, !this.#archiveView),
    );
  }
  #bindFolderFormSubmit() {
    (0, this.#home)("folder-form").addEventListener("submit", (event) =>
      this.#submitDialog(
        event,
        "folder-dialog",
        "confirm-folder",
        "folder-error",
        () =>
          MathPDFSession.api(
            this.#folderIntent
              ? `/api/library/folders/${this.#folderIntent.id}`
              : "/api/library/folders",
            this.#jsonWrite(
              this.#folderIntent ? "PATCH" : "POST",
              this.#folderIntent
                ? {
                    name: (0, this.#home)("folder-name").value,
                  }
                : {
                    name: (0, this.#home)("folder-name").value,
                    parent_id: this.#currentFolder,
                  },
            ),
          ),
      ),
    );
  }
  #bindMoveFormSubmit() {
    (0, this.#home)("move-form").addEventListener("submit", (event) =>
      this.#submitDialog(
        event,
        "move-dialog",
        "confirm-move",
        "move-error",
        () =>
          MathPDFSession.api(
            this.#moveIntent.kind === "folders"
              ? `/api/library/folders/${this.#moveIntent.id}`
              : `/api/library/items/${this.#moveIntent.kind}/${this.#moveIntent.id}`,
            this.#jsonWrite(
              "PATCH",
              this.#moveIntent.kind === "folders"
                ? {
                    parent_id:
                      (0, this.#home)("move-destination").value || null,
                  }
                : {
                    folder_id:
                      (0, this.#home)("move-destination").value || null,
                  },
            ),
          ),
      ),
    );
  }
  #bindRemoveFolderFormSubmit() {
    (0, this.#home)("remove-folder-form").addEventListener("submit", (event) =>
      this.#submitDialog(
        event,
        "remove-folder-dialog",
        "confirm-remove-folder",
        "remove-folder-error",
        async () => {
          try {
            return await MathPDFSession.api(
              `/api/library/folders/${this.#removeFolderIntent.id}`,
              {
                method: "DELETE",
                headers: {
                  "If-Match": this.#removeFolderIntent.revision,
                },
              },
            );
          } catch (error) {
            if (error.status === 409) {
              this.#removeFolderIntent = await MathPDFSession.api(
                `/api/library/folders/${this.#removeFolderIntent.id}/deletion`,
              );
              (0, this.#home)("remove-folder-message").textContent =
                `The folder changed. Review again: ${this.#removeFolderIntent.item_count} items and ${this.#removeFolderIntent.folder_count} subfolders will move to its parent.`;
            }
            throw error;
          }
        },
      ),
    );
  }
  #bindDataCloseClick() {
    for (const close of document.querySelectorAll("[data-close]"))
      close.addEventListener("click", () => {
        if (
          !close.closest("dialog").querySelector("button[type=submit]:disabled")
        )
          (0, this.#home)(close.dataset.close).close();
      });
  }
  #bindButtonTypeSubmitDisabledCancel() {
    for (const id of ["folder-dialog", "move-dialog", "remove-folder-dialog"])
      (0, this.#home)(id).addEventListener("cancel", (event) => {
        if ((0, this.#home)(id).querySelector("button[type=submit]:disabled"))
          event.preventDefault();
      });
  }
  #bindDocumentClick() {
    document.addEventListener("click", (event) => {
      for (const details of document.querySelectorAll(".item-menu[open]"))
        if (!details.contains(event.target)) details.open = false;
    });
  }
  #bindDocumentKeydown() {
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape")
        for (const details of document.querySelectorAll(".item-menu[open]"))
          details.open = false;
    });
  }
  #bindUploadFilesClick() {
    (0, this.#home)("upload-files").addEventListener(
      "click",
      this.#chooseFiles.bind(this),
    );
  }
  #bindLibraryFileInputChange() {
    (0, this.#home)("library-file-input").addEventListener("change", () => {
      const files = [...(0, this.#home)("library-file-input").files];
      (0, this.#home)("library-file-input").value = "";
      if (!files.length || this.#uploading) return;
      this.#pendingFiles.push(...files);
      this.#uploadTask = this.#uploadFiles();
    });
  }
  #registerDiagnosticContext() {
    MathPDFSession.setContextProvider?.(() => ({
      library: {
        folder_id: this.#currentFolder,
        archive_view: this.#archiveView,
        visible_files: this.#library.files
          .filter((file) =>
            this.#archiveView
              ? file.archived
              : !file.archived && file.folder_id === this.#currentFolder,
          )
          .map((file) => ({
            id: file.id,
            filename: file.filename,
            sha256: file.sha256,
          })),
        visible_sets: this.#library.sets.filter((set) =>
          this.#archiveView
            ? set.archived
            : !set.archived && set.folder_id === this.#currentFolder,
        ),
        pending_uploads: this.#pendingFiles.map((file) => ({
          name: file.name,
          size: file.size,
          type: file.type,
        })),
      },
    }));
  }
  #renderFileCard(file) {
    const entry = this.#node("article", "file-card");
    if (file.original_document_id) entry.classList.add("annotated-file");
    const link = this.#node("a", "file-card-link");
    link.href = `/workspace?${new URLSearchParams({
      document: file.id,
    })}`;
    const preview = this.#node(
        "div",
        "file-preview",
        this.#previews ? "Loading preview…" : "Preview unavailable",
      ),
      details = this.#node("div", "file-card-details");
    details.append(
      this.#node("span", "library-item-title", file.filename),
      this.#node("span", "library-item-meta", this.#fileMetadata(file)),
    );
    this.#renderOriginalCopyLabel(details, file);
    if (this.#archiveView)
      details.append(
        this.#node(
          "span",
          "library-item-meta",
          this.#locationName(file.folder_id),
        ),
      );
    link.append(preview, details);
    entry.append(link);
    const footer = this.#node("div", "file-card-footer"),
      download = this.#node("a", "library-download", "Download");
    download.href = `/api/documents/${encodeURIComponent(file.id)}/file?download=true`;
    download.setAttribute("aria-label", `Download ${file.filename}`);
    footer.append(download, this.#itemMenu("documents", file, file.filename));
    entry.append(footer);
    return this.#renderFileFooter(entry, file, preview);
  }
  #renderFolderChildren() {
    const children = this.#archiveView
      ? []
      : this.#library.folders.filter(
          (f) => f.parent_id === this.#currentFolder,
        );
    (0, this.#home)("library-folders").replaceChildren(
      ...children.map((f) => this.#renderFolderTile(f)),
    );
    (0, this.#home)("library-folders").hidden = !children.length;
  }
  #renderBreadcrumbs() {
    const crumbs = (0, this.#home)("library-breadcrumbs");
    crumbs.replaceChildren();
    const root = this.#control("Your library", "breadcrumb", () =>
      this.#navigateFolder(null),
    );
    this.#dropFolder(root, null);
    crumbs.append(root);
    for (const f of this.#archiveView
      ? [
          {
            name: "Archive",
            id: null,
          },
        ]
      : this.#folderPath(this.#currentFolder)) {
      crumbs.append(this.#node("span", "breadcrumb-divider", "/"));
      const b = this.#control(f.name, "breadcrumb", () =>
        this.#navigateFolder(f.id, this.#archiveView),
      );
      if (!this.#archiveView) this.#dropFolder(b, f.id);
      crumbs.append(b);
    }
    crumbs.lastElementChild.setAttribute("aria-current", "page");
  }
  #renderLibrarySets(sets) {
    const groups = new Map();
    for (const set of sets) {
      if (!groups.has(set.document_id))
        groups.set(set.document_id, {
          name: set.document_filename,
          items: [],
        });
      groups.get(set.document_id).items.push(set);
    }
    (0, this.#home)("library-sets").replaceChildren(
      ...[...groups].map(([id, group]) => this.#renderSourceGroup(id, group)),
    );
    if (!sets.length)
      (0, this.#home)("library-sets").append(
        this.#node(
          "p",
          "library-empty",
          this.#archiveView
            ? "No archived study sets."
            : "Study sets saved in this folder will appear here, grouped by source file.",
        ),
      );
  }
  #renderLibraryFiles(files, sets) {
    (0, this.#home)("files-count").textContent = String(files.length);
    (0, this.#home)("sets-count").textContent = String(sets.length);
    (0, this.#home)("library-files").classList.toggle(
      "file-library",
      files.length > 0,
    );
    (0, this.#home)("library-files").replaceChildren(
      ...files.map((file) => this.#renderFileCard(file)),
    );
    if (!files.length) {
      const empty = this.#node("div", "library-empty");
      empty.append(
        this.#node(
          "p",
          "",
          this.#archiveView
            ? "No archived files."
            : this.#currentFolder
              ? "No files in this folder yet."
              : "Upload a PDF to start studying.",
        ),
      );
      if (!this.#archiveView)
        empty.append(
          this.#control("Upload PDF", "", this.#chooseFiles.bind(this)),
        );
      (0, this.#home)("library-files").append(empty);
    }
  }
  #renderFileFooter(entry, file, preview) {
    this.#dragItem(entry, "documents", file.id);
    this.#previews?.observe(preview, file);
    return entry;
  }
  #renderSourceGroup(id, group) {
    const section = this.#node("details", "source-group");
    const key = `mathpdf-${MathPDFSession.user.id}-source-group-${this.#currentFolder || "root"}-${this.#archiveView}-${id}`;
    try {
      section.open = localStorage.getItem(key) !== "false";
    } catch {
      section.open = true;
    }
    const heading = this.#node("summary", "source-group-heading");
    const icon = this.#node("span", "folder-icon");
    icon.innerHTML = this.#folderIcon;
    heading.append(
      icon,
      this.#node("strong", "", group.name),
      this.#node("span", "muted", String(group.items.length)),
    );
    section.append(heading);
    section.addEventListener("toggle", () => {
      try {
        localStorage.setItem(key, String(section.open));
      } catch {}
    });
    this.#renderGroupEntries(section, group);
    return section;
  }
  async #initializeLibrary(user) {
    await this.#installNavigationGuard();
    for (const id of ["files-section", "sets-section"]) {
      const section = (0, this.#home)(id),
        key = `mathpdf-${user.id}-${id}-open`;
      try {
        section.open = localStorage.getItem(key) !== "false";
      } catch {}
      section.addEventListener("toggle", () => {
        try {
          localStorage.setItem(key, String(section.open));
        } catch {}
      });
    }
    await this.#loadLibrary();
    (0, this.#home)("upload-files").disabled = false;
  }
  async #submitDeletion(event) {
    event.preventDefault();
    if (!this.#deleteIntent) return;
    const intent = this.#deleteIntent;
    (0, this.#home)("confirm-delete").disabled = true;
    (0, this.#home)("cancel-delete").disabled = true;
    try {
      const result = await MathPDFSession.api(
        `/api/${intent.kind}/${encodeURIComponent(intent.id)}`,
        {
          method: "DELETE",
          headers: {
            "If-Match": intent.impact.revision,
          },
        },
      );
      if (result.deleted_document_id) {
        try {
          const { clearVisualCache } = await import("/static/visual-cache.js");
          for (const id of result.deleted_document_ids || [
            result.deleted_document_id,
          ])
            await clearVisualCache(MathPDFSession.user.id, id);
        } catch {}
      }
      (0, this.#home)("delete-dialog").close();
      this.#deleteIntent = null;
      await this.#loadLibrary();
    } catch (error) {
      if (error.status === 409) {
        try {
          intent.impact = await MathPDFSession.api(
            `/api/${intent.kind}/${encodeURIComponent(intent.id)}/deletion`,
          );
          this.#showDeletion(intent.impact);
        } catch {}
      }
      (0, this.#home)("delete-error").textContent = error.message;
      (0, this.#home)("delete-error").hidden = false;
    } finally {
      (0, this.#home)("confirm-delete").disabled = false;
      (0, this.#home)("cancel-delete").disabled = false;
    }
  }
  #renderGroupEntries(section, group) {
    const list = this.#node("div", "source-group-list");
    for (const set of group.items) {
      const kind =
        set.mode === "flashcards"
          ? set.item_count === 1
            ? "flashcard"
            : "flashcards"
          : set.item_count === 1
            ? "problem"
            : "problems";
      const date = new Date(set.updated_at).toLocaleDateString("en-GB", {
        day: "numeric",
        month: "short",
        year: "numeric",
      });
      const meta = `${set.item_count} ${kind} · Level ${set.difficulty} · Saved ${date}${this.#archiveView ? " · " + this.#locationName(set.folder_id) : ""}`;
      const entry = this.#row(
        set.title,
        meta,
        `/workspace?${new URLSearchParams({
          set: set.id,
        })}`,
      );
      entry.append(this.#itemMenu("study-sets", set, set.title));
      this.#dragItem(entry, "study-sets", set.id);
      list.append(entry);
    }
    section.append(list);
  }
  #renderOriginalCopyLabel(details, file) {
    if (file.original_document_id) {
      details.prepend(this.#node("span", "edited-copy-label", "Edited copy"));
      const original = this.#library.files.find(
        (x) => x.id === file.original_document_id,
      );
      if (original)
        details.append(
          this.#node("span", "library-item-meta", `From ${original.filename}`),
        );
    }
  }
  async #installNavigationGuard() {
    const { createLeaveGuard } = await import("/static/leave-guard.js");
    const leave = createLeaveGuard({
      pending: () =>
        this.#pendingFiles.map((file) => `${file.name} · Not uploaded`),
      save: async () => {
        if (!this.#uploading && this.#pendingFiles.length)
          this.#uploadTask = this.#uploadFiles();
        await this.#uploadTask;
        if (this.#pendingFiles.length)
          throw (
            this.#uploadFailure ||
            new Error("Some files could not be uploaded.")
          );
      },
    });
    MathPDFSession.setLeaveGuard(
      () => leave.confirm(),
      () => leave.reset(),
    );
    document.addEventListener("click", (event) => {
      const link = event.target.closest("a[href]");
      if (
        !link ||
        event.button !== 0 ||
        event.ctrlKey ||
        event.metaKey ||
        event.shiftKey ||
        event.altKey
      )
        return;
      const url = new URL(link.href);
      if (
        url.origin !== location.origin ||
        !["/", "/workspace"].includes(url.pathname)
      )
        return;
      event.preventDefault();
      leave
        .confirm()
        .then((ok) => {
          if (ok) location.assign(url.href);
        })
        .catch(this.#showError.bind(this));
    });
  }
  #renderFolderTile(f) {
    const tile = this.#node("article", "folder-tile");
    const open = this.#control(
      "",
      "folder-open",
      () => this.#navigateFolder(f.id),
      `Open folder ${f.name}`,
    );
    const icon = this.#node("span", "folder-icon");
    icon.innerHTML = this.#folderIcon;
    const copy = this.#node("span", "folder-copy");
    copy.append(this.#node("strong", "", f.name));
    const files = this.#library.files.filter(
        (x) => !x.archived && x.folder_id === f.id,
      ).length,
      sets = this.#library.sets.filter(
        (x) => !x.archived && x.folder_id === f.id,
      ).length;
    copy.append(
      this.#node(
        "small",
        "muted",
        `${files} ${files === 1 ? "file" : "files"} · ${sets} ${sets === 1 ? "set" : "sets"}`,
      ),
    );
    open.append(icon, copy);
    tile.append(
      open,
      this.#menu(f.name, [
        ["Rename", () => this.#showFolder(f)],
        ["Move", () => this.#showMove("folders", f.id, f.name, f.parent_id)],
        ["Remove folder", () => this.#showRemoveFolder(f), true],
      ]),
    );
    this.#dragItem(tile, "folders", f.id);
    this.#dropFolder(tile, f.id);
    return tile;
  }
  async #uploadPendingFiles(targetFolder, failures) {
    let completed = 0;
    for (const file of [...this.#pendingFiles]) {
      this.#diagnosticItem = {
        file_name: file.name,
      };
      (0, this.#home)("upload-status").textContent = `Uploading ${file.name}…`;
      try {
        if (file.size > 25 * 1024 * 1024)
          throw new Error("The file exceeds 25 MB.");
        const body = new FormData();
        body.append("file", file);
        const uploaded = await MathPDFSession.api("/api/documents", {
          method: "POST",
          body,
        });
        await MathPDFSession.api(
          `/api/library/items/documents/${uploaded.id}`,
          this.#jsonWrite("PATCH", {
            folder_id: targetFolder,
            archived: false,
          }),
        );
        completed++;
        this.#pendingFiles = this.#pendingFiles.filter(
          (pending) => pending !== file,
        );
      } catch (error) {
        failures.push(`${file.name}: ${error.message}`);
      }
    }
    return [completed];
  }
}
new LibraryController();

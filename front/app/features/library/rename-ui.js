class RenameDialog {
  constructor() {
    this.#make = (tag, text, cls) => {
      const e = document.createElement(tag);
      if (text) e.textContent = text;
      if (cls) e.className = cls;
      return e;
    };
    this.#dialog = (0, this.#make)("dialog");
    this.#form = (0, this.#make)("form");
    this.#header = (0, this.#make)("div", null, "dialog-header");
    this.#title = (0, this.#make)("h2");
    this.#body = (0, this.#make)("div", null, "dialog-body");
    this.#label = (0, this.#make)("label", "Name");
    this.#input = (0, this.#make)("input");
    this.#note = (0, this.#make)("p", null, "field-note");
    this.#error = (0, this.#make)("p", null, "error");
    this.#title.id = "rename-heading";
    this.#dialog.setAttribute("aria-labelledby", this.#title.id);
    this.#input.id = "rename-name";
    this.#label.htmlFor = this.#input.id;
    this.#input.maxLength = 200;
    this.#input.required = true;
    this.#input.autocomplete = "off";
    this.#error.setAttribute("role", "alert");
    this.#header.append(this.#title);
    this.#body.append(this.#label, this.#input, this.#note, this.#error);
    this.#footer = (0, this.#make)("div", null, "dialog-footer");
    this.#cancel = (0, this.#make)("button", "Cancel", "secondary");
    this.#save = (0, this.#make)("button", "Save name");
    this.#cancel.type = "button";
    this.#save.type = "submit";
    this.#footer.append(this.#cancel, this.#save);
    this.#form.append(this.#header, this.#body, this.#footer);
    this.#dialog.append(this.#form);
    document.body.append(this.#dialog);
    this.#intent = undefined;
    this.#busy = false;
    this.#bindCancelClick();
    this.#bindDialogCancel();
    this.#bindFormSubmit();
  }
  #make;
  #dialog;
  #form;
  #header;
  #title;
  #body;
  #label;
  #input;
  #note;
  #error;
  #footer;
  #cancel;
  #save;
  #intent;
  #busy;
  #bindCancelClick() {
    this.#cancel.addEventListener("click", () => {
      if (!this.#busy) this.#dialog.close();
    });
  }
  #bindDialogCancel() {
    this.#dialog.addEventListener("cancel", (event) => {
      if (this.#busy) event.preventDefault();
    });
  }
  #bindFormSubmit() {
    this.#form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (this.#busy || !this.#intent) return;
      this.#busy = true;
      this.#save.disabled = this.#cancel.disabled = true;
      this.#error.hidden = true;
      try {
        await this.#intent.save(this.#input.value);
        this.#dialog.close();
      } catch (failure) {
        this.#error.textContent = failure.message;
        this.#error.hidden = false;
      } finally {
        this.#busy = false;
        this.#save.disabled = this.#cancel.disabled = false;
      }
    });
  }
  get api() {
    return {
      open: (...args) => this.#api_open(...args),
    };
  }
  #api_open({ name, kind, save: apply }) {
    this.#intent = {
      save: apply,
    };
    this.#title.textContent =
      kind === "documents" ? "Rename file" : "Rename study set";
    this.#input.value = name;
    this.#note.textContent =
      kind === "documents"
        ? "The file type stays the same. The extension will be kept automatically."
        : "Your cards, solutions and progress keep their existing identifiers.";
    this.#error.hidden = true;
    this.#dialog.showModal();
    this.#input.focus();
    this.#input.select();
  }
}
/* One accessible name dialog for library items and workspace tabs. */
export function createRenameDialog() {
  return new RenameDialog().api;
}

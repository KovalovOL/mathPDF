class LeaveGuard {
  constructor({ pending, save }) {
    this.#pending = pending;
    this.#save = save;
    this.#createLeaveDialog();
    this.#createLeaveActions();
    this.#saving = false;
    this.#approved = false;
    this.#confirmation = undefined;
    this.#bindCancelClick();
    this.#bindDiscardClick();
    this.#bindDialogCancel();
    this.#bindPersistClick();
    addEventListener("beforeunload", (event) => {
      if (this.#approved) {
        this.#approved = false;
        return;
      }
      if ((0, this.#pending)().length) {
        event.preventDefault();
        event.returnValue = "";
      }
    });
    addEventListener("pageshow", () => {
      this.#approved = false;
    });
  }
  #pending;
  #save;
  #dialog;
  #heading;
  #body;
  #message;
  #list;
  #status;
  #error;
  #footer;
  #cancel;
  #discard;
  #persist;
  #saving;
  #approved;
  #confirmation;
  #refresh() {
    this.#list.replaceChildren(
      ...(0, this.#pending)().map((label) => {
        const item = document.createElement("li");
        item.textContent = label;
        return item;
      }),
    );
  }
  #busy(value) {
    this.#saving = value;
    for (const button of [this.#cancel, this.#discard, this.#persist])
      button.disabled = value;
    this.#status.hidden = !value;
    this.#status.textContent = value ? "Saving your work…" : "";
    this.#dialog.setAttribute("aria-busy", String(value));
  }
  #bindCancelClick() {
    this.#cancel.addEventListener("click", () => this.#dialog.close("cancel"));
  }
  #bindDiscardClick() {
    this.#discard.addEventListener("click", () => this.#dialog.close("leave"));
  }
  #bindDialogCancel() {
    this.#dialog.addEventListener("cancel", (event) => {
      if (this.#saving) event.preventDefault();
    });
  }
  #bindPersistClick() {
    this.#persist.addEventListener("click", async () => {
      if (this.#saving) return;
      this.#busy(true);
      this.#error.hidden = true;
      try {
        await (0, this.#save)();
        if ((0, this.#pending)().length)
          throw new Error(
            "Some work is still unsaved. Save or finish it before leaving.",
          );
        this.#dialog.close("leave");
      } catch (failure) {
        this.#refresh();
        this.#error.textContent = failure.message;
        this.#error.hidden = false;
      } finally {
        this.#busy(false);
      }
    });
  }
  get api() {
    return {
      reset: (...args) => this.#api_reset(...args),
      confirm: (...args) => this.#api_confirm(...args),
    };
  }
  #api_reset() {
    this.#approved = false;
  }
  #api_confirm() {
    if (this.#confirmation) return this.#confirmation;
    if (!(0, this.#pending)().length) {
      this.#approved = true;
      return Promise.resolve(true);
    }
    this.#refresh();
    this.#error.hidden = true;
    this.#busy(false);
    this.#dialog.returnValue = "cancel";
    this.#dialog.showModal();
    this.#confirmation = new Promise((resolve) =>
      this.#dialog.addEventListener(
        "close",
        () => {
          this.#approved = this.#dialog.returnValue === "leave";
          this.#confirmation = null;
          resolve(this.#approved);
        },
        {
          once: true,
        },
      ),
    );
    return this.#confirmation;
  }
  #createLeaveActions() {
    this.#footer = document.createElement("div");
    this.#footer.className = "dialog-footer annotation-choice-actions";
    this.#cancel = document.createElement("button");
    this.#discard = document.createElement("button");
    this.#persist = document.createElement("button");
    for (const button of [this.#cancel, this.#discard, this.#persist])
      button.type = "button";
    this.#cancel.textContent = "Cancel";
    this.#cancel.className = "secondary";
    this.#cancel.autofocus = true;
    this.#discard.textContent = "Leave without saving";
    this.#discard.className = "secondary";
    this.#persist.textContent = "Save and leave";
    this.#footer.append(this.#cancel, this.#discard, this.#persist);
    this.#dialog.append(this.#heading, this.#body, this.#footer);
    document.body.append(this.#dialog);
  }
  #createLeaveDialog() {
    this.#dialog = document.createElement("dialog");
    this.#dialog.id = "leave-dialog";
    this.#dialog.setAttribute("aria-labelledby", "leave-heading");
    this.#heading = document.createElement("h2");
    this.#heading.id = "leave-heading";
    this.#heading.className = "dialog-header";
    this.#heading.textContent = "Save before leaving?";
    this.#body = document.createElement("div");
    this.#body.className = "dialog-body";
    this.#message = document.createElement("p");
    this.#message.textContent =
      "You have unsaved work. Save it before leaving this page?";
    this.#list = document.createElement("ul");
    this.#status = document.createElement("p");
    this.#error = document.createElement("p");
    this.#status.className = "field-note";
    this.#status.setAttribute("role", "status");
    this.#status.hidden = true;
    this.#error.className = "error";
    this.#error.setAttribute("role", "alert");
    this.#error.hidden = true;
    this.#body.append(this.#message, this.#list, this.#status, this.#error);
  }
}
/* Save pending workspace content before an intentional in-app departure. */
export function createLeaveGuard({ pending, save }) {
  return new LeaveGuard({
    pending,
    save,
  }).api;
}

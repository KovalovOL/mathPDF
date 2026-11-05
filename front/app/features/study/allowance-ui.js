/* Shared daily-allowance meter and recoverable generation-limit dialog. */
const node = (tag, text, cls) => {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  if (cls) e.className = cls;
  return e;
};
function resetText(state, now = Date.now()) {
  const minutes = Math.max(
    0,
    Math.ceil((Date.parse(state.resets_at) - now) / 60000),
  );
  return `Resets in ${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, "0")}m · 00:00 UTC`;
}
function renderMeter(target, state, { compact = false } = {}) {
  target.replaceChildren();
  target.hidden = !state?.limited;
  if (target.hidden) return;
  const left = Math.max(0, Math.min(100, Number(state.remaining_percent) || 0)),
    used = Number((100 - left).toFixed(1));
  target.dataset.level = left === 0 ? "empty" : left <= 20 ? "low" : "normal";
  const heading = node("div", undefined, "allowance-heading");
  if (!compact) heading.append(node("span", "Daily AI allowance"));
  heading.append(node("strong", `${left}% left`, "allowance-left"));
  const track = node("div", undefined, "allowance-track"),
    fill = node("span", undefined, "allowance-fill");
  fill.style.width = `${left}%`;
  track.append(fill);
  track.setAttribute("role", "progressbar");
  track.setAttribute("aria-label", "Daily generation allowance remaining");
  track.setAttribute("aria-valuemin", "0");
  track.setAttribute("aria-valuemax", "100");
  track.setAttribute("aria-valuenow", String(left));
  track.setAttribute("aria-valuetext", `${left}% remaining, ${used}% used`);
  target.append(heading, track);
  if (compact) {
    target.title = `Daily AI allowance: ${left}% left. ${resetText(state)}${state.reserved_tokens > 0 ? ". Pending or unconfirmed generations are included." : ""}`;
    return;
  }
  const legend = node("div", undefined, "allowance-legend"),
    usedLabel = node("span", `${used}% used`, "allowance-used-label"),
    reset = node("span", resetText(state), "allowance-reset");
  legend.append(usedLabel, reset);
  target.append(legend);
  if (state.reserved_tokens > 0)
    target.append(
      node(
        "p",
        "Pending or unconfirmed generations are included.",
        "allowance-pending",
      ),
    );
}
class AllowanceController {
  constructor({ api }) {
    this.#api = api;
    this.#header = document.querySelector(".app-header");
    this.#actions = this.#header?.querySelector(".header-actions");
    this.#state = undefined;
    this.#refreshing = undefined;
    this.#bar = node("section", undefined, "allowance-header");
    this.#bar.setAttribute("aria-label", "Daily generation allowance");
    this.#bar.tabIndex = 0;
    this.#bar.hidden = true;
    this.#primary = this.#actions?.querySelector(
      "#open-generation,#upload-files",
    );
    if (this.#primary) this.#primary.before(this.#bar);
    else (this.#actions || this.#header)?.prepend(this.#bar);
    this.#visible = () => {
      if (!document.hidden) this.#refresh();
    };
    this.#timer = setInterval(this.#tick.bind(this), 60000);
    addEventListener("mathpdf-allowance-changed", this.#refresh.bind(this));
    this.#bindDocumentVisibilitychange();
  }
  #api;
  #header;
  #actions;
  #state;
  #refreshing;
  #bar;
  #primary;
  #visible;
  #timer;
  #draw() {
    renderMeter(this.#bar, this.#state, {
      compact: true,
    });
    for (const box of document.querySelectorAll("[data-generation-allowance]"))
      renderMeter(box, this.#state);
    dispatchEvent(
      new CustomEvent("mathpdf-allowance-updated", {
        detail: this.#state,
      }),
    );
  }
  async #refresh() {
    if (this.#refreshing) return this.#refreshing;
    this.#refreshing = (async () => {
      try {
        this.#state = await (0, this.#api)("/api/generation/allowance");
        this.#draw();
      } catch {
      } finally {
        this.#refreshing = null;
      }
    })();
    return this.#refreshing;
  }
  #tick() {
    if (document.hidden) return;
    if (this.#state?.limited && Date.now() >= Date.parse(this.#state.resets_at))
      this.#refresh();
    else if (this.#state) this.#draw();
  }
  #bindDocumentVisibilitychange() {
    document.addEventListener("visibilitychange", this.#visible);
  }
  get api() {
    return {
      refresh: this.#refresh.bind(this),
      destroy: (...args) => this.#api_destroy(...args),
    };
  }
  #api_destroy() {
    clearInterval(this.#timer);
    this.#bar.remove();
    removeEventListener("mathpdf-allowance-changed", this.#refresh.bind(this));
    document.removeEventListener("visibilitychange", this.#visible);
  }
}
export function createAllowanceUI({ api }) {
  return new AllowanceController({
    api,
  }).api;
}
class GenerationLimitDialog {
  constructor({ onAdjust }) {
    this.#onAdjust = onAdjust;
    this.#dialog = node("dialog", undefined, "allowance-dialog");
    this.#dialog.setAttribute("aria-labelledby", "allowance-dialog-title");
    this.#body = node("div", undefined, "allowance-dialog-body");
    this.#icon = node("div", "◷", "allowance-dialog-icon");
    this.#icon.setAttribute("aria-hidden", "true");
    this.#title = node("h2");
    this.#title.id = "allowance-dialog-title";
    this.#description = node("p", undefined, "allowance-description");
    this.#meter = node("div", undefined, "generation-allowance");
    this.#tip = node("p", undefined, "allowance-tip");
    this.#actions = node("div", undefined, "dialog-footer");
    this.#close = node("button", "Close", "secondary");
    this.#adjust = node("button", "Adjust request");
    this.#close.type = this.#adjust.type = "button";
    this.#bindCloseClick();
    this.#bindAdjustClick();
    this.#actions.append(this.#close, this.#adjust);
    this.#body.append(
      this.#icon,
      this.#title,
      this.#description,
      this.#meter,
      this.#tip,
    );
    this.#dialog.append(this.#body, this.#actions);
    document.body.append(this.#dialog);
    this.#failure = undefined;
    addEventListener("mathpdf-allowance-updated", (event) => {
      if (!this.#dialog.open || !this.#failure || !event.detail) return;
      this.#failure = {
        ...this.#failure,
        allowance: event.detail,
      };
      this.#draw();
    });
  }
  #onAdjust;
  #dialog;
  #body;
  #icon;
  #title;
  #description;
  #meter;
  #tip;
  #actions;
  #close;
  #adjust;
  #failure;
  #draw() {
    if (!this.#failure) return;
    const state = this.#failure.allowance,
      disabled = state.limited && state.daily_tokens === 0,
      ready =
        !state.limited ||
        (!disabled &&
          (this.#failure.reason === "insufficient"
            ? typeof this.#failure.required_percent === "number" &&
              this.#failure.required_percent <= state.remaining_percent
            : state.remaining_percent > 0));
    this.#title.textContent = disabled
      ? "Generation is paused for your plan"
      : ready
        ? "Your allowance is ready"
        : this.#failure.reason === "insufficient"
          ? "This request needs more allowance"
          : "You've used today's allowance";
    this.#description.textContent = disabled
      ? "Your free plan currently has no generation allowance."
      : ready
        ? "You can return to your settings and generate your study set."
        : this.#failure.reason === "insufficient"
          ? `You have ${state.remaining_percent}% left. A smaller request may fit your remaining daily allowance.`
          : "Your full daily allowance will be available again at 00:00 UTC.";
    renderMeter(this.#meter, state);
    const estimate =
      typeof this.#failure.required_percent === "number"
        ? `Estimated request: ${this.#failure.required_percent}% of your daily allowance. `
        : "";
    this.#tip.textContent = disabled
      ? "Your administrator can update your daily allowance."
      : ready
        ? "Your selected files, pages and comments are still there."
        : this.#failure.reason === "insufficient"
          ? this.#failure.required_percent > 100
            ? "This request exceeds a full daily allowance. Select fewer pages, fewer items or less additional context."
            : estimate +
              "Try fewer pages, fewer items or less additional context."
          : "Come back after the reset. Your selected files, pages and comments are still there.";
    this.#adjust.hidden = disabled;
    this.#adjust.textContent = ready ? "Continue" : "Adjust request";
  }
  #bindCloseClick() {
    this.#close.addEventListener("click", () => this.#dialog.close());
  }
  #bindAdjustClick() {
    this.#adjust.addEventListener("click", () => {
      this.#dialog.close();
      (0, this.#onAdjust)();
    });
  }
  get api() {
    return {
      show: (...args) => this.#api_show(...args),
    };
  }
  #api_show(error) {
    this.#failure = error;
    this.#draw();
    if (!this.#dialog.open) this.#dialog.showModal();
    this.#adjust.hidden ? this.#close.focus() : this.#adjust.focus();
  }
}
export function createGenerationLimitDialog({ onAdjust }) {
  return new GenerationLimitDialog({
    onAdjust,
  }).api;
}

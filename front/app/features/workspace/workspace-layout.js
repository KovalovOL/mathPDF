class WorkspaceLayout {
  constructor({ preference, onViewport }) {
    this.#preference = preference;
    this.#onViewport = onViewport;
    this.#workspace = document.getElementById("workspace");
    this.#source = document.getElementById("document-pane");
    this.#practice = document.getElementById("practice-pane");
    this.#splitter = document.getElementById("splitter");
    this.#hide = document.getElementById("hide-source");
    this.#show = document.getElementById("show-source");
    this.#mobile = matchMedia("(max-width: 640px)");
    this.#ratio = Number((0, this.#preference)("split-ratio")) || 0.5;
    this.#desktopCollapsed =
      (0, this.#preference)("source-collapsed") === "true";
    this.#mobileCollapsed = false;
    this.#gesture = undefined;
    this.#collapsed = () =>
      this.#mobile.matches ? this.#mobileCollapsed : this.#desktopCollapsed;
    this.#bindHideClick();
    this.#bindShowClick();
    this.#bindSplitterPointerdown();
    this.#bindSplitterPointermove();
    this.#bindSplitterPointerup();
    this.#bindSplitterPointercancel();
    this.#bindSplitterLostpointercapture();
    this.#bindSplitterKeydown();
    this.#resizeTimer = undefined;
    addEventListener("resize", () => {
      this.#apply(false);
      clearTimeout(this.#resizeTimer);
      this.#resizeTimer = setTimeout(() => (0, this.#onViewport)(true), 150);
    });
    this.#bindMobileChange();
    this.#scrollFrame = undefined;
    this.#bindWindowScroll();
    this.#bindPracticeTouchstart();
    this.#bindPracticeTouchmove();
    this.#bindPracticeTouchend();
    this.#bindPracticeTouchcancel();
    this.#apply();
  }
  #preference;
  #onViewport;
  #workspace;
  #source;
  #practice;
  #splitter;
  #hide;
  #show;
  #mobile;
  #ratio;
  #desktopCollapsed;
  #mobileCollapsed;
  #gesture;
  #collapsed;
  #resizeTimer;
  #scrollFrame;
  #apply(settled = true) {
    this.#workspace.classList.toggle(
      "source-collapsed",
      (0, this.#collapsed)(),
    );
    this.#source.inert = (0, this.#collapsed)();
    this.#source.setAttribute("aria-hidden", String((0, this.#collapsed)()));
    this.#hide.setAttribute("aria-expanded", String(!(0, this.#collapsed)()));
    this.#show.hidden = !(0, this.#collapsed)();
    if (!this.#mobile.matches && !(0, this.#collapsed)()) {
      const width = this.#workspace.clientWidth - 32;
      const minimum = Math.max(0.2, 240 / width),
        maximum = Math.min(0.8, (width - 280) / width);
      this.#ratio = Math.min(maximum, Math.max(minimum, this.#ratio));
      this.#workspace.style.setProperty(
        "--source-size",
        `${this.#ratio * 100}%`,
      );
    }
    this.#splitter.setAttribute(
      "aria-valuenow",
      (0, this.#collapsed)() ? "0" : String(Math.round(this.#ratio * 100)),
    );
    this.#splitter.setAttribute("aria-valuemin", "0");
    this.#splitter.setAttribute("aria-valuemax", "80");
    (0, this.#onViewport)(settled);
  }
  #collapseSource() {
    if (this.#mobile.matches) this.#mobileCollapsed = true;
    else {
      this.#desktopCollapsed = true;
      (0, this.#preference)("source-collapsed", true);
    }
    this.#apply();
    if (this.#mobile.matches) scrollTo(0, 0);
    this.#show.focus({
      preventScroll: true,
    });
  }
  #showSource({ scroll = false } = {}) {
    if (this.#mobile.matches) this.#mobileCollapsed = false;
    else {
      this.#desktopCollapsed = false;
      (0, this.#preference)("source-collapsed", false);
    }
    this.#apply();
    if (this.#mobile.matches && scroll)
      window.scrollTo({
        top: 0,
        behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "instant"
          : "smooth",
      });
  }
  #resize(value) {
    if (this.#mobile.matches) return;
    if (value <= 0.06) {
      this.#collapseSource();
      return;
    }
    this.#desktopCollapsed = false;
    (0, this.#preference)("source-collapsed", false);
    this.#ratio = value;
    this.#apply(false);
  }
  #finish(event) {
    if (this.#splitter.hasPointerCapture(event.pointerId))
      this.#splitter.releasePointerCapture(event.pointerId);
    document.body.classList.remove("resizing");
    (0, this.#preference)("split-ratio", this.#ratio);
    (0, this.#onViewport)(true);
  }
  #atTop(target) {
    if (
      getSelection()?.toString() ||
      target.closest("a, button, input, textarea, select, summary")
    )
      return false;
    for (
      let node = target;
      node && node !== this.#practice;
      node = node.parentElement
    ) {
      if (node.scrollTop > 1 || node.scrollLeft > 1) return false;
    }
    return true;
  }
  #bindHideClick() {
    this.#hide.addEventListener("click", this.#collapseSource.bind(this));
  }
  #bindShowClick() {
    this.#show.addEventListener("click", () => {
      this.#showSource({
        scroll: true,
      });
      this.#hide.focus({
        preventScroll: true,
      });
    });
  }
  #bindSplitterPointerdown() {
    this.#splitter.addEventListener("pointerdown", (event) => {
      if (event.button !== 0 || this.#mobile.matches) return;
      event.preventDefault();
      this.#splitter.setPointerCapture(event.pointerId);
      document.body.classList.add("resizing");
    });
  }
  #bindSplitterPointermove() {
    this.#splitter.addEventListener("pointermove", (event) => {
      if (!this.#splitter.hasPointerCapture(event.pointerId)) return;
      const box = this.#workspace.getBoundingClientRect();
      this.#resize((event.clientX - box.left - 12) / (box.width - 32));
    });
  }
  #bindSplitterPointerup() {
    this.#splitter.addEventListener("pointerup", this.#finish.bind(this));
  }
  #bindSplitterPointercancel() {
    this.#splitter.addEventListener("pointercancel", this.#finish.bind(this));
  }
  #bindSplitterLostpointercapture() {
    this.#splitter.addEventListener("lostpointercapture", () => {
      document.body.classList.remove("resizing");
      (0, this.#preference)("split-ratio", this.#ratio);
      (0, this.#onViewport)(true);
    });
  }
  #bindSplitterKeydown() {
    this.#splitter.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key))
        return;
      event.preventDefault();
      this.#resize(
        event.key === "Home"
          ? 0
          : event.key === "End"
            ? 0.8
            : this.#ratio + (event.key === "ArrowRight" ? 0.03 : -0.03),
      );
      (0, this.#preference)("split-ratio", this.#ratio);
    });
  }
  #bindMobileChange() {
    this.#mobile.addEventListener("change", () => this.#apply());
  }
  #bindWindowScroll() {
    addEventListener(
      "scroll",
      () => {
        if (!this.#mobile.matches || (0, this.#collapsed)()) return;
        cancelAnimationFrame(this.#scrollFrame);
        this.#scrollFrame = requestAnimationFrame(() => {
          const header = document
            .querySelector(".app-header")
            .getBoundingClientRect().bottom;
          if (
            scrollY > 40 &&
            this.#practice.getBoundingClientRect().top <= header + 12
          )
            this.#collapseSource();
        });
      },
      {
        passive: true,
      },
    );
  }
  #bindPracticeTouchstart() {
    this.#practice.addEventListener(
      "touchstart",
      (event) => {
        this.#gesture =
          this.#mobile.matches &&
          (0, this.#collapsed)() &&
          event.touches.length === 1 &&
          this.#atTop(event.target)
            ? {
                x: event.touches[0].clientX,
                y: event.touches[0].clientY,
              }
            : null;
      },
      {
        passive: true,
      },
    );
  }
  #bindPracticeTouchmove() {
    this.#practice.addEventListener(
      "touchmove",
      (event) => {
        if (
          !this.#gesture ||
          event.touches.length !== 1 ||
          !this.#atTop(event.target)
        )
          return;
        const touch = event.touches[0];
        if (
          touch.clientY - this.#gesture.y > 65 &&
          Math.abs(touch.clientX - this.#gesture.x) < 45
        ) {
          event.preventDefault();
          this.#gesture = null;
          this.#showSource({
            scroll: true,
          });
        }
      },
      {
        passive: false,
      },
    );
  }
  #bindPracticeTouchend() {
    this.#practice.addEventListener(
      "touchend",
      () => {
        this.#gesture = null;
      },
      {
        passive: true,
      },
    );
  }
  #bindPracticeTouchcancel() {
    this.#practice.addEventListener(
      "touchcancel",
      () => {
        this.#gesture = null;
      },
      {
        passive: true,
      },
    );
  }
  get api() {
    return {
      showSource: this.#showSource.bind(this),
      collapseSource: this.#collapseSource.bind(this),
    };
  }
}
/* Source-pane layout only; document instances and study content remain mounted. */
export function createWorkspaceLayout({ preference, onViewport }) {
  return new WorkspaceLayout({
    preference,
    onViewport,
  }).api;
}

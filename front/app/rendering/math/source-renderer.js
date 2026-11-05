class SourceRenderer {
  constructor() {
    this.#loadedFonts = new Map();
    this.#baselineOffsets = new Map();
    window.FormulaLab = {
      render: this.#render.bind(this),
      loadFonts: this.#loadFonts.bind(this),
    };
  }
  #loadedFonts;
  #baselineOffsets;
  async #loadFonts(formula) {
    for (const font of formula.fonts) {
      if (!font.url) continue;
      if (!this.#loadedFonts.has(font.id)) {
        const promise = new FontFace(font.id, `url("${font.url}")`)
          .load()
          .then((face) => document.fonts.add(face));
        this.#loadedFonts.set(font.id, promise);
        promise.catch(() => this.#loadedFonts.delete(font.id));
      }
      await this.#loadedFonts.get(font.id);
    }
  }
  #baselineOffset(node) {
    const key = `${node.font_id}|${node.size}`;
    if (!this.#baselineOffsets.has(key)) {
      // Browser line boxes round font metrics. Measure a real baseline instead
      // of assuming that a nominal 0.8em ascent survives that rounding.
      const probe = document.createElement("div"),
        marker = document.createElement("span");
      Object.assign(probe.style, {
        position: "absolute",
        left: "-9999px",
        top: "0",
        visibility: "hidden",
        margin: "0",
        padding: "0",
        border: "0",
        fontFamily: `"${node.font_id}"`,
        fontSize: `${node.size}px`,
        fontWeight: "normal",
        fontStyle: "normal",
        lineHeight: "1",
        whiteSpace: "pre",
      });
      probe.append(document.createTextNode(node.text));
      Object.assign(marker.style, {
        display: "inline-block",
        width: "0",
        height: "0",
        padding: "0",
        margin: "0",
        verticalAlign: "baseline",
      });
      probe.append(marker);
      document.body.append(probe);
      this.#baselineOffsets.set(
        key,
        marker.getBoundingClientRect().top - probe.getBoundingClientRect().top,
      );
      probe.remove();
    }
    return this.#baselineOffsets.get(key);
  }
  async #render(container, formula, scale = 2, onSelect = null) {
    await this.#loadFonts(formula);
    const fonts = new Map(formula.fonts.map((f) => [f.id, f]));
    const plane = document.createElement("div");
    plane.className = "formula-plane";
    plane.style.width = `${formula.width * scale}px`;
    plane.style.height = `${formula.height * scale}px`;
    plane.setAttribute("role", "math");
    for (const node of formula.nodes) {
      const element = document.createElement(
        node.kind === "text" ? "span" : "div",
      );
      element.dataset.nodeId = node.id;
      if (node.kind === "text") {
        this.#styleSourceGlyph(node, element, scale, fonts);
        if (["+", "−", "-"].includes(node.text) && onSelect) {
          element.classList.add("sign");
          element.addEventListener("click", () => onSelect(node.id));
        }
      } else {
        element.className = "math-rule";
        Object.assign(element.style, {
          left: `${node.x * scale}px`,
          top: `${node.y * scale}px`,
          width: `${node.width * scale}px`,
          height: `${node.height * scale}px`,
          background: node.color,
        });
      }
      plane.append(element);
    }
    container.replaceChildren(plane);
    container.style.width = `${formula.width * scale}px`;
    container.style.height = `${formula.height * scale}px`;
    return plane;
  }
  #styleSourceGlyph(node, element, scale, fonts) {
    element.className = "math-token";
    element.textContent = node.text;
    const size = node.size * scale;
    Object.assign(element.style, {
      left: `${node.x * scale}px`,
      top: `${
        node.y * scale -
        this.#baselineOffset({
          ...node,
          size,
        })
      }px`,
      fontFamily: `"${node.font_id}"`,
      fontSize: `${size}px`,
      color: node.color,
      transform: `scaleX(${node.x_scale})`,
      fontFeatureSettings: node.feature ? `"${node.feature}" 1` : "normal",
    });
    element.title = `${node.text} · ${node.id} · ${node.glyph_name}`;
    if (!fonts.get(node.font_id)?.url || node.glyph_name === "unsupported") {
      element.classList.add("unsupported");
      element.textContent = "�";
      element.title = "Unsupported source glyph or font";
    }
  }
}
/* Optional source-font diagnostic renderer. */
new SourceRenderer();

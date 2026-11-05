/** Uses the same study projection and math renderer as the interactive UI. */
class StudyPrint {
  #result;
  #options;
  async run() {
    try {
      this.#result = JSON.parse(
        document.getElementById("study-data").textContent,
      );
      this.#header();
      for (const [index, item] of this.#result.items.entries())
        this.#item(item, index);
      await document.fonts.ready;
      for (const output of document.querySelectorAll(".math-output"))
        this.#fit(output);
      document.documentElement.dataset.exportStatus = "ready";
    } catch (error) {
      document.getElementById("export-error").textContent = error.message;
      document.documentElement.dataset.exportStatus = "error";
    }
  }
  #element(tag, text) {
    const node = document.createElement(tag);
    node.textContent = text;
    return node;
  }
  #header() {
    const result = this.#result;
    document.title = result.title;
    document.getElementById("title").textContent = result.title;
    document.getElementById("source").textContent =
      `${result.document.filename} · source pages ${result.pages.join(", ")}`;
    this.#options = {
      editable: false,
      linkSources: false,
      sourceLabel: (ref) => `${result.document.filename} · page ${ref.page}`,
    };
  }
  #item(item, index) {
    const card = this.#result.mode === "flashcards";
    const content = card ? MathPDF.flashcardSides(item) : item;
    for (const side of ["question", "answer"]) {
      const section = document.createElement("section");
      section.className = "print-item";
      section.append(
        this.#element(
          "h3",
          card && side === "question"
            ? `Card ${index + 1}`
            : `${index + 1}. ${item.title}`,
        ),
      );
      const blocks = document.createElement("div");
      MathPDF.renderBlocks(blocks, content[side], this.#options);
      section.append(blocks);
      if (side === "answer") this.#answerDetails(section, content);
      document
        .getElementById(side === "question" ? "questions" : "answers")
        .append(section);
    }
  }
  #answerDetails(section, content) {
    if (content.source)
      section.append(MathPDF.citation(content.source, this.#options));
    for (const block of MathPDF.variantBlocks(content)) {
      section.append(this.#element("p", block.change));
      section.append(
        MathPDF.mathBlock(
          {
            ...block,
            latex: block.original_latex,
          },
          this.#options,
        ),
      );
    }
  }
  #fit(output) {
    if (output.scrollWidth <= output.clientWidth + 1) return;
    const ratio = output.clientWidth / output.scrollWidth;
    if (ratio < 0.5)
      throw new Error(
        "A formula is too wide for the PDF page. Split it into aligned lines before exporting.",
      );
    output.style.fontSize = `${16 * ratio * 0.98}px`;
    if (output.scrollWidth > output.clientWidth + 2)
      throw new Error(
        "A formula does not fit the PDF page. Adjust its layout before exporting.",
      );
  }
}
new StudyPrint().run();

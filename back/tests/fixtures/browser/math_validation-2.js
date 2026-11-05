(text) => {
  const container = document.createElement("div");
  MathPDF.renderBlocks(container, [{ kind: "text", text }], {
    editable: false,
  });
  return {
    latex: [
      ...container.querySelectorAll('annotation[encoding="application/x-tex"]'),
    ].map((n) => n.textContent),
    errors: container.querySelectorAll(".math-fallback").length,
    plain: [...container.querySelector("p").childNodes]
      .filter((n) => n.nodeType === 3)
      .map((n) => n.textContent)
      .join(""),
  };
};

(latex) => {
  const target = document.createElement("div");
  const ok = MathPDF.renderMath(target, latex, true);
  const normalized = target.querySelector("annotation")?.textContent;
  const repeat = document.createElement("div");
  const idempotent =
    MathPDF.renderMath(repeat, normalized, true) &&
    repeat.querySelector("annotation")?.textContent === normalized;
  return {
    ok,
    latex: normalized,
    idempotent,
    ampersands: (
      target.querySelector(".katex-html")?.textContent.match(/&/g) || []
    ).length,
  };
};

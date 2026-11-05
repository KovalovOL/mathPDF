(latex) => {
  const target = document.createElement("div");
  const ok = MathPDF.renderMath(target, latex, true);
  return { ok, latex: target.querySelector("annotation")?.textContent };
};

() => {
  const good = document.createElement("div"),
    bad = document.createElement("div");
  return {
    good: MathPDF.renderMath(good, "x+\\text{a label", false),
    source: good.querySelector("annotation")?.textContent,
    bad: MathPDF.renderMath(bad, "\\overline{x", false),
    raw: bad.textContent,
  };
};

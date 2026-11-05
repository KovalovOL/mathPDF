(item) => {
  const before = JSON.stringify(item),
    sides = MathPDF.flashcardSides(item);
  const front = document.createElement("div"),
    back = document.createElement("div");
  MathPDF.renderBlocks(front, sides.question, { editable: false });
  MathPDF.renderBlocks(back, sides.answer, { editable: false });
  return {
    unchanged: before === JSON.stringify(item),
    idempotent:
      JSON.stringify(MathPDF.flashcardSides(sides)) === JSON.stringify(sides),
    frontMath: front.querySelectorAll(
      ".inline-math, .math-block, .math-fallback",
    ).length,
    frontText: front.textContent,
    answerBlocks: sides.answer,
    backMath: back.querySelectorAll(".katex, .math-fallback").length,
  };
};

(node) => {
  const p = new DOMPoint(
    node.cx.baseVal.value,
    node.cy.baseVal.value,
  ).matrixTransform(node.getScreenCTM());
  const target = new DOMPoint(200, 300).matrixTransform(
    node.parentNode.getScreenCTM(),
  );
  return Math.hypot(p.x - target.x, p.y - target.y);
};

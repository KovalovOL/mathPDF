() => {
  const text = document.querySelector(".textLayer span").firstChild,
    range = document.createRange();
  range.setStart(text, 0);
  range.setEnd(text, 11);
  getSelection().removeAllRanges();
  getSelection().addRange(range);
};

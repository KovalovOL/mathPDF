({ target, horizontal }) => {
  const element = document.querySelector(target);
  function send(type, x, y) {
    const touch = new Touch({
      identifier: 1,
      target: element,
      clientX: x,
      clientY: y,
    });
    return element.dispatchEvent(
      new TouchEvent(type, {
        bubbles: true,
        cancelable: true,
        touches: [touch],
      }),
    );
  }
  send("touchstart", 100, 140);
  send("touchmove", 100 + horizontal, 230);
  element.dispatchEvent(
    new TouchEvent("touchend", { bubbles: true, touches: [] }),
  );
  return document
    .querySelector("#workspace")
    .classList.contains("source-collapsed");
};

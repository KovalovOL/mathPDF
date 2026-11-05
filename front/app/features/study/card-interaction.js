/* Card gestures stay independent from rendering, generation and review storage. */
export class FlashcardInteraction {
  #card;
  #flip;
  #previous;
  #next;
  #start;
  #touch = false;
  #moved = false;
  constructor(card, { flip, previous, next }) {
    this.#card = card;
    this.#flip = flip;
    this.#previous = previous;
    this.#next = next;
    card.addEventListener("pointerdown", (event) => this.#pointerDown(event));
    card.addEventListener("pointermove", (event) => this.#pointerMove(event));
    card.addEventListener("pointercancel", () => {
      this.#moved = true;
      this.#start = null;
    });
    card.addEventListener("click", (event) => this.#click(event));
    card.addEventListener("keydown", (event) => this.#key(event));
  }
  #pointerDown(event) {
    this.#touch = event.pointerType === "touch";
    this.#moved = this.#touch && event.isPrimary === false;
    this.#start = this.#touch
      ? {
          x: event.clientX,
          y: event.clientY,
        }
      : null;
  }
  #pointerMove(event) {
    if (
      this.#start &&
      Math.hypot(event.clientX - this.#start.x, event.clientY - this.#start.y) >
        8
    )
      this.#moved = true;
  }
  #click(event) {
    if (event.target.closest("a,button,input,textarea,select,summary")) return;
    if (this.#moved) {
      this.#moved = false;
      this.#start = null;
      return;
    }
    const selection = window.getSelection();
    if (
      !this.#touch &&
      selection?.toString() &&
      this.#card.contains(selection.anchorNode)
    )
      return;
    if (
      this.#touch &&
      selection?.toString() &&
      this.#card.contains(selection.anchorNode)
    )
      selection.removeAllRanges();
    this.#start = null;
    this.#touch = false;
    this.#flip();
  }
  #key(event) {
    if (event.target !== this.#card) return;
    const action =
      event.code === "Space" || event.key === "Enter"
        ? this.#flip
        : event.key === "ArrowLeft"
          ? this.#previous
          : event.key === "ArrowRight"
            ? this.#next
            : null;
    if (action) {
      event.preventDefault();
      action();
    }
  }
}
export function wireFlashcard(card, actions) {
  new FlashcardInteraction(card, actions);
}

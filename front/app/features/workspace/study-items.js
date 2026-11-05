export class StudyItemsView {
  #makeElement;
  #makeButton;
  #renderAnswer;
  #sourceOptions;
  #selectItem;
  #reviewUI;
  #wireFlashcard;

  constructor({
    makeElement,
    makeButton,
    renderAnswer,
    sourceOptions,
    selectItem,
    reviewUI,
    wireFlashcard,
  }) {
    this.#makeElement = makeElement;
    this.#makeButton = makeButton;
    this.#renderAnswer = renderAnswer;
    this.#sourceOptions = sourceOptions;
    this.#selectItem = selectItem;
    this.#reviewUI = reviewUI;
    this.#wireFlashcard = wireFlashcard;
  }

  render(record, result, item) {
    if (result.mode === "flashcards") {
      const summary = this.#reviewUI()?.summary(record);
      return summary && !record.reviewBrowse
        ? summary
        : this.#flashcard(record, item);
    }
    return this.#problem(item, result);
  }

  #flashcard(record, original) {
    const item = MathPDF.flashcardSides(original);
    const deck = this.#makeElement("div", "deck");
    const card = this.#makeElement("section", "flashcard");
    card.tabIndex = 0;
    card.setAttribute(
      "aria-label",
      `Card ${record.itemIndex + 1}. Press Space to flip this card.`,
    );
    const inner = this.#makeElement("div", "card-inner");
    const front = this.#makeElement("div", "card-face card-front");
    const back = this.#makeElement("div", "card-face card-back");
    this.#front(item, record, front);
    this.#back(item, record, back);
    inner.append(front, back);
    card.append(inner);
    const assessment = this.#reviewUI()?.controls(record);
    const [navigation, counter] = this.#navigation(record, assessment);
    this.#bindFlip(card, front, back, counter, record, assessment);
    deck.append(card, navigation);
    return deck;
  }

  #bindFlip(card, front, back, counter, record, assessment) {
    const update = () => {
      assessment?.update(!!record.flipped);
      counter.hidden = !!record.flipped;
      card.classList.toggle("flipped", !!record.flipped);
      front.inert = !!record.flipped;
      back.inert = !record.flipped;
      front.setAttribute("aria-hidden", String(!!record.flipped));
      back.setAttribute("aria-hidden", String(!record.flipped));
    };
    const flip = () => {
      record.flipped = !record.flipped;
      update();
    };
    this.#wireFlashcard(card, {
      flip,
      previous: () => this.#selectItem(record.itemIndex - 1),
      next: () => this.#selectItem(record.itemIndex + 1),
    });
    update();
  }

  #navigation(record, assessment) {
    const navigation = this.#makeElement("div", "deck-footer");
    navigation.setAttribute(
      "aria-label",
      "Card navigation and self-assessment",
    );
    const previous = this.#makeButton("‹", "secondary icon-button", () =>
      this.#selectItem(record.itemIndex - 1),
    );
    const next = this.#makeButton("›", "secondary icon-button", () =>
      this.#selectItem(record.itemIndex + 1),
    );
    previous.setAttribute("aria-label", "Previous card");
    next.setAttribute("aria-label", "Next card");
    previous.disabled = record.itemIndex === 0;
    next.disabled = record.itemIndex === record.data.items.length - 1;
    const center = this.#makeElement("div", "deck-footer-center");
    const counter = this.#makeElement(
      "span",
      "deck-counter",
      `${record.itemIndex + 1} / ${record.data.items.length}`,
    );
    center.append(counter);
    if (assessment) center.append(assessment.root);
    navigation.append(previous, center, next);
    return [navigation, counter];
  }

  #front(item, record, target) {
    const label = this.#cardLabel("Question", record);
    const body = this.#makeElement("div", "card-body");
    const question = this.#makeElement("div", "card-blocks");
    MathPDF.renderBlocks(question, item.question, { editable: false });
    body.append(question);
    target.append(
      label,
      body,
      this.#makeElement(
        "p",
        "card-hint",
        "Tap the card or press Space to reveal",
      ),
    );
  }

  #back(item, record, target) {
    const label = this.#cardLabel("Answer", record);
    const body = this.#makeElement("div", "card-body");
    body.append(this.#makeElement("h2", "", item.title));
    const answer = this.#makeElement("div", "card-blocks");
    this.#renderAnswer(answer, item, record.data);
    body.append(answer);
    target.append(
      label,
      body,
      this.#makeElement("p", "card-hint", "Click to return to the question"),
    );
  }

  #cardLabel(text, record) {
    const label = this.#makeElement("div", "card-label");
    label.append(
      this.#makeElement("span", "", text),
      this.#makeElement(
        "span",
        "",
        `${record.itemIndex + 1} / ${record.data.items.length}`,
      ),
    );
    return label;
  }

  #problem(item, result) {
    const problem = this.#makeElement("article", "problem");
    problem.append(this.#makeElement("h2", "", item.title));
    const question = this.#makeElement("div");
    MathPDF.renderBlocks(question, item.question, this.#sourceOptions(result));
    const solution = this.#makeElement("details", "solution");
    solution.append(this.#makeElement("summary", "", "Solution"));
    const answer = this.#makeElement("div");
    this.#renderAnswer(answer, item, result);
    solution.append(answer);
    problem.append(question, solution);
    return problem;
  }
}

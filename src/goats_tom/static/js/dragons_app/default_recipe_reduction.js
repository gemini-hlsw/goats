/**
 * Template class for creating the default recipe reduction card.
 * Responsible for rendering the static UI components of the card.
 */
class DefaultRecipeReductionTemplate {
  constructor() {}

  /**
   * Creates a container element.
   * @returns {HTMLElement} The container element.
   * @private
   */
  _createContainer() {
    // Don't show anything until a recipe is selected.
    const container = Utils.createElement("div");
    return container;
  }

  /**
   * Creates the entire card component.
   * @returns {HTMLElement} The card container with its header, body, and footer.
   */
  create() {
    const container = this._createContainer();
    const card = this._createCard();

    container.appendChild(card);
    return container;
  }

  /**
   * Creates the card structure with header, body, and footer.
   * @returns {HTMLElement} The card element.
   * @private
   */
  _createCard() {
    const card = Utils.createElement("div", ["card"]);
    card.append(
      this._createCardHeader(),
      this._createCardBody(),
      this._createCardFooter()
    );

    return card;
  }

  /**
   * Creates the card header with a title.
   * @returns {HTMLElement} The card header element.
   * @private
   */
  _createCardHeader() {
    const cardHeader = Utils.createElement("div", "card-header");
    const row = Utils.createElement("div", ["row"]);
    const col = Utils.createElement("div", ["col"]);
    const p = Utils.createElement("p", ["my-0", "h5"]);
    p.textContent = "Select an Available Recipe to Continue";
    col.appendChild(p);
    row.appendChild(col);
    cardHeader.appendChild(row);

    return cardHeader;
  }

  /**
   * Creates the card body with descriptive content.
   * @returns {HTMLElement} The card body element.
   * @private
   */
  _createCardBody() {
    const cardBody = document.createElement("div");
    cardBody.className = "card-body";

    // Add descriptive content to the card body
    const cardText = `
      <p>Select an available recipe to populate this recipe card. This recipe card will allow you to:</p>
      <ul>
        <li>Start and stop a DRAGONS reduction.</li>
        <li>Modify the recipe's primitives and passed-in arguments.</li>
        <li>Provide optional parameters applied to the entire recipe.</li>
        <li>See the log from DRAGONS in real-time as the reduction continues.</li>
      </ul>
      <p>This happens in the background, allowing you to perform other tasks while it runs.</p>
    `;
    cardBody.innerHTML = cardText;

    return cardBody;
  }
  /**
   * Creates the card footer with a spinning GOATS emoji.
   * @returns {HTMLElement} The card footer element.
   * @private
   */
  _createCardFooter() {
    const cardFooter = document.createElement("div");
    cardFooter.className = "card-footer text-center";
    cardFooter.innerHTML = `
      <div class="d-flex flex-column align-items-center">
        <div class="goat-spinner" style="font-size: 2rem;">🐐</div>
      </div>
    `;

    return cardFooter;
  }
}

/**
 * Class for managing the default recipe reduction card.
 * Handles showing and hiding the card in the user interface.
 * @param {HTMLElement} parentElement - The parent element to which the card will be appended.
 */
class DefaultRecipeReduction {
  // TODO: Would be a good entry point to learn MVC to convert this.
  constructor(parentElement) {
    this.template = new DefaultRecipeReductionTemplate();
    this.container = null;
    this._init(parentElement);
  }
  /**
   * Initializes the card by creating and appending it to the parent element.
   * @param {HTMLElement} parentElement - The parent element to which the card will be appended.
   * @private
   */
  _init(parentElement) {
    this._create(parentElement);
  }
  /**
   * Creates the card and appends it to the parent element.
   * @param {HTMLElement} parentElement - The parent element to which the card will be appended.
   * @private
   */
  _create(parentElement) {
    this.container = this.template.create();
    parentElement.appendChild(this.container);
  }
  /**
   * Hides the card.
   */
  hide() {
    this.container.classList.add("d-none");
  }
  /**
   * Shows the card.
   */
  show() {
    this.container.classList.remove("d-none");
  }
}

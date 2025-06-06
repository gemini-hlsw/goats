class RecipesAndFilesManagerTemplate {
  constructor(options) {
    this.options = options;
  }

  create() {
    const container = this._createContainer();
    const card = this._createCard();

    container.appendChild(card);

    return container;
  }

  /**
   * Creates a container element.
   * @returns {HTMLElement} The container element.
   * @private
   */
  _createContainer() {
    const container = Utils.createElement("div");
    return container;
  }

  /**
   * Creates a card container.
   * @return {HTMLElement} The card element.
   */
  _createCard() {
    const card = Utils.createElement("div", ["card"]);
    card.append(this._createCardHeader(), this._createCardBody());

    return card;
  }

  /**
   * Creates the header section of the card.
   * @returns {HTMLElement} The card header element
   */
  _createCardHeader() {
    const div = Utils.createElement("div", ["card-header", "h5", "mb-0"]);
    div.textContent = "Available Recipes and Files";

    return div;
  }

  /**
   * Creates the body section of the card.
   * @return {HTMLElement} The card body element.
   */
  _createCardBody() {
    const cardBody = Utils.createElement("div", ["card-body"]);
    const accordion = Utils.createElement("div", ["accordion", "accordion-flush"]);
    accordion.id = "observationTypeManagerAccordion";
    cardBody.appendChild(accordion);
    return cardBody;
  }

  /**
   * Creates an accordion for collapsible content.
   * @return {HTMLElement} The accordion element.
   */
  createAccordion(recipesData, filesData, groupsData, identifier) {
    const accordion = Utils.createElement("div", ["accordion-item"]);

    const header = Utils.createElement("h6", ["accordion-header"]);
    const headerId = `${identifier.idPrefix}header${this.options.id}`;
    header.id = headerId;

    const button = Utils.createElement("button");
    const collapseId = `${identifier.idPrefix}collapse${this.options.id}`;
    button.className = "accordion-button collapsed";
    button.setAttribute("type", "button");
    button.setAttribute("data-bs-toggle", "collapse");
    button.setAttribute("data-bs-target", `#${collapseId}`);
    button.setAttribute("aria-expanded", "false");
    button.setAttribute("aria-controls", collapseId);
    button.textContent = identifier.displayText;

    header.appendChild(button);

    const collapseDiv = Utils.createElement("div");
    collapseDiv.id = collapseId;
    collapseDiv.className = "accordion-collapse collapse";
    collapseDiv.setAttribute("aria-labelledby", headerId);
    collapseDiv.setAttribute("data-bs-parent", "#observationTypeManagerAccordion");

    const accordionBody = Utils.createElement("div", [
      "accordion-body",
      "accordion-body-overflow",
    ]);

    // Create the available recipes.
    new AvailableRecipes(accordionBody, recipesData);

    // FIXME: Create the available files.
    new AvailableFiles(
      accordionBody,
      { files: filesData, groups: groupsData },
      identifier
    );

    collapseDiv.appendChild(accordionBody);
    accordion.append(header, collapseDiv);

    return accordion;
  }
}

class RecipesAndFilesManagerModel {
  constructor(options) {
    this.options = options;
    this.api = this.options.api;
    this._groupsData = null;
    this._data = null;
    this._recipesAndFilesData = null;
    this._runId = null;
    this.url = "dragonsdata/";
  }

  set runId(value) {
    this._runId = value;
  }

  get runId() {
    return this._runId;
  }

  set data(value) {
    this._data = value;
    this._groupsData = value.groups;
    this._recipesAndFilesData = value.recipes_and_files;
  }

  get data() {
    return this._data;
  }

  get groupsData() {
    return this._groupsData;
  }

  get recipesAndFilesData() {
    return this._recipesAndFilesData;
  }

  async fetchData() {
    try {
      const response = await this.api.get(`${this.url}${this.runId}`);
      this.data = response;
    } catch (error) {
      console.error("Error fetching list of recipes:", error);
      throw error;
    }
  }
}

class RecipesAndFilesManagerView {
  constructor(template, options) {
    this.template = template;
    this.options = options;

    this.container = null;
    this.availableFiles = null;
    this.availableRecipes = null;
    this.parentElement = null;
    this.render = this.render.bind(this);
    this.bindCallback = this.bindCallback.bind(this);
  }

  _create(parentElement, runId, recipesAndFilesData, groupsData) {
    this.container = this.template.create();
    this.cardBody = this.container.querySelector(".accordion");
    this._createAccordions(runId, recipesAndFilesData, groupsData);

    this.parentElement = parentElement;
    this.parentElement.appendChild(this.container);
  }
  _createAccordions(runId, recipesAndFilesData, groupsData) {
    // Build the accordions with the data.
    const { observation_type } = recipesAndFilesData; // Destructure to get observation types directly
    // Loop through each observation_type
    Object.entries(observation_type).forEach(([observationType, classes]) => {
      // Loop through each observation_class under the current observation_type.
      Object.entries(classes).forEach(([observationClass, objects]) => {
        // Loop through each object_name under the current observation_class.
        Object.entries(objects).forEach(([objectName, content]) => {
          const { recipes, files } = content; // Destructure to get recipes and files for the object

          // Check if there are recipes and files to display
          if (recipes.length === 0 && files.length === 0) return; // Skip if no recipes and no files

          // Create identifier to use for each nested data.
          const identifier = new Identifier(
            runId,
            observationType,
            observationClass,
            objectName
          );
          // Build the accordion item
          const accordion = this.template.createAccordion(
            recipes,
            files,
            groupsData,
            identifier
          );
          this.cardBody.appendChild(accordion);
        });
      });
    });
  }

  _update(runId, recipesAndFilesData, groupsData) {
    this._clearCardBody();
    this._createAccordions(runId, recipesAndFilesData, groupsData);
  }

  _clearCardBody() {
    this.cardBody.innerHTML = "";
  }

  render(viewCmd, parameter) {
    switch (viewCmd) {
      case "create":
        this._create(
          parameter.parentElement,
          parameter.runId,
          parameter.recipesAndFilesData,
          parameter.groupsData
        );
        break;
      case "update":
        this._update(
          parameter.runId,
          parameter.recipesAndFilesData,
          parameter.groupsData
        );
        break;
    }
  }

  bindCallback(event, handler) {}
}

class RecipesAndFilesManagerController {
  constructor(model, view, options) {
    this.model = model;
    this.view = view;
    this.options = options;
  }

  async create(parentElement, runId) {
    this.model.runId = runId;
    await this.model.fetchData();
    this.view.render("create", {
      parentElement,
      runId,
      recipesAndFilesData: this.model.recipesAndFilesData,
      groupsData: this.model.groupsData,
    });

    this._bindCallbacks();
  }

  async update(runId) {
    this.model.runId = runId;
    await this.model.fetchData();
    this.view.render("update", {
      runId,
      recipesAndFilesData: this.model.recipesAndFilesData,
      groupsData: this.model.groupsData,
    });
  }

  _bindCallbacks() {}
}

class RecipesAndFilesManager {
  static #defaultOptions = {
    id: "RecipesAndFilesManager",
  };

  constructor(parentElement, runId, options = {}) {
    this.options = {
      ...RecipesAndFilesManager.#defaultOptions,
      ...options,
      api: window.api,
    };
    const model = new RecipesAndFilesManagerModel(this.options);
    const template = new RecipesAndFilesManagerTemplate(this.options);
    const view = new RecipesAndFilesManagerView(template, parentElement, this.options);
    this.controller = new RecipesAndFilesManagerController(model, view, this.options);

    this._create(parentElement, runId);
  }

  update(runId) {
    this.controller.update(runId);
  }

  /**
   * Initializes the available files component.
   * @param {HTMLElement} parentElement - The parent element to append the files to.
   * @param {Object} runId - The runId to initialize the component with.
   * @private
   */
  _create(parentElement, runId) {
    this.controller.create(parentElement, runId);
  }
}

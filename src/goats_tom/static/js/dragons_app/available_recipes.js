/**
 * Create a template.
 * @param {Object} options - The options for the template.
 */
class AvailableRecipesTemplate {
  constructor(options) {
    this.options = options;
  }

  /**
   * Create the main structure for available recipes.
   * @param {Array} data - The data for the recipes.
   * @returns {HTMLElement} The container element with the created structure.
   */
  create(data) {
    const container = this._createContainer();
    const title = this._createTitle();
    const nav = this._createNav(data);

    container.append(title, nav);

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
   * Create the navigation structure for available recipes.
   * @param {Array} data - The data for the recipes.
   * @returns {HTMLElement} The nav element.
   * @private
   */
  _createNav(data) {
    const title = Utils.createElement("p", "mb-2");
    title.textContent = "Available Recipes";

    const nav = Utils.createElement("ul", ["nav", "nav-pills", "flex-column"]);
    nav.setAttribute("role", "tablist");
    nav.setAttribute("aria-orientation", "vertical");

    data.forEach((recipe) => {
      const navItem = this._createNavItem(recipe);
      nav.appendChild(navItem);
    });

    return nav;
  }

  /**
   * Create the title element for available recipes.
   * @returns {HTMLElement} The title element.
   * @private
   */
  _createTitle() {
    const title = Utils.createElement("p", "mb-2");
    title.textContent = "Available Recipes";

    return title;
  }

  /**
   * Create a nav item for each recipe.
   * @param {Object} data - The data for the recipe.
   * @returns {HTMLElement} The nav item element.
   * @private
   */
  _createNavItem(data) {
    const pillId = `pill${data.id}${this.options.id}`;
    const paneId = `pane${data.id}${this.options.id}`;

    const navItem = Utils.createElement("li", "nav-item");
    navItem.setAttribute("role", "presentation");

    const navLink = Utils.createElement("button", [
      "nav-link",
      "w-100",
      "text-start",
      "d-flex",
      "align-items-center",
    ]);
    navLink.setAttribute("id", pillId);
    navLink.setAttribute("data-bs-toggle", "pill");
    navLink.setAttribute("data-bs-target", `#${paneId}`);
    navLink.setAttribute("type", "button");
    navLink.setAttribute("role", "tab");
    navLink.setAttribute("aria-controls", paneId);
    navLink.setAttribute("aria-selected", "false");
    navLink.dataset.action = "selectRecipe";
    navLink.dataset.recipeId = data.id;

    if (data.observation_type !== "other") {
      navLink.textContent = `${data.short_name}${data.is_default ? " (default)" : ""}`;
    } else {
      navLink.classList.add("disabled");
      navLink.textContent = data.short_name;
    }

    navItem.appendChild(navLink);
    return navItem;
  }
}
/**
 * Create a model.
 * @param {Object} options - The options for the model.
 */
class AvailableRecipesModel {
  constructor(options) {
    this.options = options;
  }
}

/**
 * Create a view.
 * @param {Object} template - The template for the view.
 * @param {Object} options - The options for the view.
 */
class AvailableRecipesView {
  constructor(template, options) {
    this.template = template;
    this.options = options;

    this.container = null;
    this.recipesNav = null;

    this.parentElement = null;

    this.render = this.render.bind(this);
    this.bindCallback = this.bindCallback.bind(this);
    this.bindGlobalCallback = this.bindGlobalCallback.bind(this);
  }

  /**
   * Create the view's HTML structure.
   * @param {Array} data - The data for the recipes.
   * @param {HTMLElement} parentElement - The parent element to append the container to.
   * @private
   */
  _create(data, parentElement) {
    this.container = this.template.create(data);
    this.recipesNav = this.container.querySelector(".nav");
    this.parentElement = parentElement;

    // Append the container to the parent element.
    this.parentElement.appendChild(this.container);
  }

  /**
   * Update the active recipe in the UI.
   * @param {number} recipeId - The ID of the recipe to update.
   * @private
   */
  _updateRecipe(recipeId) {
    // Remove active class from currently active tab.
    const currentActive = this.recipesNav.querySelector(".nav-link.active");
    if (currentActive) {
      currentActive.classList.remove("active");
    }

    // Add active class to the selected tab.
    const newActive = this.recipesNav.querySelector(`[data-recipe-id="${recipeId}"]`);
    if (newActive) {
      newActive.classList.add("active");
    }
  }

  /**
   * Render the view based on the command and parameters.
   * @param {string} viewCmd - The command to execute in the view.
   * @param {Object} parameter - The parameters for the view command.
   */
  render(viewCmd, parameter) {
    switch (viewCmd) {
      case "updateRecipe":
        this._updateRecipe(parameter.recipeId);
        break;
      case "create":
        this._create(parameter.data, parameter.parentElement);
    }
  }

  /**
   * Bind a local callback to a specific event.
   * @param {string} event - The event to bind.
   * @param {function} handler - The function to handle the event.
   */
  bindCallback(event, handler) {
    const selector = `[data-action="${event}"]`;
    switch (event) {
      case "selectRecipe":
        Utils.delegate(this.recipesNav, selector, "click", (e) => {
          const recipeId = e.target.dataset.recipeId;
          handler({ recipeId });
        });
        break;
    }
  }

  /**
   * Bind a global callback to a specific event.
   * @param {string} event - The event to bind.
   * @param {function} handler - The function to handle the event.
   */
  bindGlobalCallback(event, handler) {
    switch (event) {
      case "updateRecipe":
        document.addEventListener("updateRecipe", (e) => {
          const recipeId = e.detail.recipeId;
          handler({ recipeId });
        });
        break;
    }
  }
}

/**
 * Create a controller.
 * @param {Object} model - The model for the controller.
 * @param {Object} view - The view for the controller.
 * @param {Object} options - The options for the controller.
 */
class AvailableRecipesController {
  constructor(model, view, options) {
    this.model = model;
    this.view = view;
    this.options = options;
  }

  /**
   * Create the data and bind the necessary callbacks.
   * @param {Array} data - The data for the recipes.
   * @param {HTMLElement} parentElement - The parent element.
   */
  create(data, parentElement) {
    this.view.render("create", { data, parentElement });
    this._bindCallbacks();
    this._bindGlobalCallbacks();
  }

  /**
   * Bind local callbacks for recipe selection.
   * @private
   */
  _bindCallbacks() {
    this.view.bindCallback("selectRecipe", (item) => this._selectRecipe(item.recipeId));
  }

  /**
   * Bind global callbacks for recipe updates.
   * @private
   */
  _bindGlobalCallbacks() {
    this.view.bindGlobalCallback("updateRecipe", (item) =>
      this._updateRecipe(item.recipeId)
    );
  }

  /**
   * Handle the recipe selection event and dispatch a global event.
   * @param {number} recipeId - The ID of the selected recipe.
   * @private
   */
  _selectRecipe(recipeId) {
    const event = new CustomEvent("updateRecipe", {
      detail: { recipeId },
    });
    // Dispatch the event globally on the document.
    document.dispatchEvent(event);
  }

  /**
   * Update the selected recipe.
   * @param {number} recipeId - The ID of the recipe to update.
   * @private
   */
  _updateRecipe(recipeId) {
    this.view.render("updateRecipe", { recipeId });
  }
}

/**
 * Create the available recipes for an observation type.
 * @param {HTMLElement} parentElement - The parent element to contain the app.
 * @param {Array} data - The data for the recipes.
 * @param {Object} [options={}] - The options for the app.
 */
class AvailableRecipes {
  static #defaultOptions = {
    id: "AvailableRecipes",
  };
  constructor(parentElement, data, options = {}) {
    this.options = { ...AvailableRecipes.#defaultOptions, ...options };
    const model = new AvailableRecipesModel(this.options);
    const template = new AvailableRecipesTemplate(this.options);
    const view = new AvailableRecipesView(template, parentElement, this.options);
    this.controller = new AvailableRecipesController(model, view, this.options);

    this._create(data, parentElement);
  }

  /**
   * Initialize and create the available recipes structure.
   * @param {Array} data - The data for the recipes.
   * @param {HTMLElement} parentElement - The parent element to append the structure to.
   * @private
   */
  _create(data, parentElement) {
    this.controller.create(data, parentElement);
  }
}

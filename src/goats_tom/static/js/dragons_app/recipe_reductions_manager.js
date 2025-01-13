class RecipeReductionsManagerModel {
  constructor(options) {
    this.options = options;
    this.api = options.api;
    this._currentRecipeId = null;
    this._runId = null;
    this.url = "dragonsrecipes/";
    this.reducesUrl = "dragonsreduce/";
  }

  get runId() {
    return this._runId;
  }

  set runId(value) {
    this._runId = value;
  }

  get currentRecipeId() {
    return this._currentRecipeId;
  }

  set currentRecipeId(value) {
    this._currentRecipeId = value;
  }

  async fetchRecipes() {
    try {
      const response = await this.api.get(`${this.url}?dragons_run=${this.runId}`);
      return response.results;
    } catch (error) {
      console.error("Error fetching list of recipes:", error);
      throw error;
    }
  }
  async fetchRunningReduces() {
    try {
      const response = await this.api.get(
        `${this.reducesUrl}?not_finished=true&run=${this.runId}`
      );
      // Transform the API data into WebSocket-like payloads.
      return response.results.map((item) => ({
        update: "recipe",
        status: item.status,
        recipe_id: item.recipe,
        reduce_id: item.id,
        run_id: this.runId,
      }));
    } catch (error) {
      console.error("Error fetching initial statuses:", error);
      return [];
    }
  }
}

class RecipeReductionsManagerTemplate {
  constructor(options) {
    this.options = options;
  }
}

class RecipeReductionsManagerView {
  constructor(template, options) {
    this.template = template;
    this.options = options;

    this.container = null;
    // Store all the recipe reductions.
    this.recipeReductions = new Map();
    this.defaultRecipeReduction = null;
  }

  render(viewCmd, parameter) {
    switch (viewCmd) {
      case "create":
        this._create(parameter.parentElement, parameter.data);
        break;
      case "updateRecipe":
        this._updateRecipe(parameter.recipeId);
        break;
      case "update":
        this._update(parameter.data);
        break;
      case "updateRecipeReductionLog":
        this._updateRecipeReductionLog(parameter.recipeId, parameter.message);
        break;
      case "updateRecipeReduction":
        this._updateRecipeReduction(parameter.recipeId, parameter.data);
        break;
    }
  }

  _updateRecipeReductionLog(recipeId, message) {
    const recipeReduction = this._getRecipeReduction(recipeId);
    if (recipeReduction) {
      recipeReduction.log(message);
    }
  }

  _getRecipeReduction(recipeId) {
    return this.recipeReductions.get(String(recipeId));
  }

  _updateRecipeReduction(recipeId, data) {
    const recipeReduction = this._getRecipeReduction(recipeId);
    if (recipeReduction) {
      recipeReduction.update(data);
    }
  }

  _updateRecipe(recipeId) {
    // TODO: Improve this to cache what is already shown to prevent looping.
    // Iterate through all entries in the map
    this.defaultRecipeReduction.hide();
    this.recipeReductions.forEach((recipeReduction, id) => {
      if (id === recipeId) {
        recipeReduction.show();
      } else {
        recipeReduction.hide();
      }
    });
  }

  _create(parentElement, data) {
    this.parentElement = parentElement;
    // Create default recipe card.
    this.defaultRecipeReduction = new DefaultRecipeReduction(this.parentElement);

    // Loop through and create recipe reductions.
    data.forEach((recipe) => {
      // Use map for accessing.
      this.recipeReductions.set(
        String(recipe.id),
        new RecipeReduction(parentElement, recipe)
      );
    });
  }

  _update(data) {
    console.log("CALLED UPDATE")
    // First, remove all HTML elements associated with the entries in the map.
    while (this.parentElement.firstChild) {
      this.parentElement.removeChild(this.parentElement.firstChild);
    }
    this.defaultRecipeReduction = null;

    // Second, clear the map itself.
    this.recipeReductions.clear();
    // Recreate the elements.
    this._create(this.parentElement, data);
  }

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

class RecipeReductionsManagerController {
  constructor(model, view, options) {
    this.model = model;
    this.view = view;
    this.options = options;
  }

  _bindGlobalCallbacks() {
    this.view.bindGlobalCallback("updateRecipe", (item) => {
      this._updateRecipe(item.recipeId);
    });
  }

  async create(parentElement, runId) {
    this.model.runId = runId;
    const data = await this.model.fetchRecipes();
    this.view.render("create", { parentElement, data });
    this._setupWebSocket();
    this._bindGlobalCallbacks();

    // Fetch the initial values.
    const runningData = await this.model.fetchRunningReduces();
    runningData.forEach((item) => {
      this._wsUpdateRecipeReduction(item.recipe_id, item);
    });
  }

  async update(runId) {
    this.model.runId = runId;
    const data = await this.model.fetchRecipes();
    this.view.render("update", { data });

    // Fetch the initial values.
    const runningData = await this.model.fetchRunningReduces();
    runningData.forEach((item) => {
      this._wsUpdateRecipeReduction(item.recipe_id, item);
    });
  }

  _updateRecipe(recipeId) {
    if (this.model.currentRecipeId !== recipeId) {
      this.view.render("updateRecipe", { recipeId });
      this.model.currentRecipeId = recipeId;
    }
  }

  _wsUpdateRecipeReductionLog(recipeId, message) {
    // TODO: This updates off screen as well, do we want that?
    this.view.render("updateRecipeReductionLog", { recipeId, message });
  }

  _wsUpdateRecipeReduction(recipeId, data) {
    // TODO: This updates off screen as well, do we want that?
    this.view.render("updateRecipeReduction", { recipeId, data });
  }

  _setupWebSocket() {
    const wsProtocol = window.location.protocol === "https:" ? "wss" : "ws";
    const wsUrl = `${wsProtocol}://${window.location.host}/ws/dragons/`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.update === "log") {
        this._wsUpdateRecipeReductionLog(data.recipe_id, data.message);
      }
      if (data.update === "recipe") {
        this._wsUpdateRecipeReduction(data.recipe_id, data);
      }
    };

    this.ws.onopen = () => {
      console.log("DRAGONS WebSocket connection established");
    };

    this.ws.onclose = (event) => {
      console.log("DRAGONS WebSocket connection closed", event);
    };

    this.ws.onerror = (error) => {
      console.log("DRAGONS WebSocket error", error);
    };
  }
}

class RecipeReductionsManager {
  static #defaultOptions = {
    id: "RecipeReductionsManager",
  };

  constructor(parentElement, runId, options = {}) {
    this.options = {
      ...RecipeReductionsManager.#defaultOptions,
      ...options,
      api: window.api,
    };
    const model = new RecipeReductionsManagerModel(this.options);
    const template = new RecipeReductionsManagerTemplate(this.options);
    const view = new RecipeReductionsManagerView(template, this.options);
    this.controller = new RecipeReductionsManagerController(model, view, this.options);

    this._init(parentElement, runId, data);
  }

  _init(parentElement, runId) {
    this._create(parentElement, runId);
  }

  _create(parentElement, runId, data) {
    this.controller.create(parentElement, runId);
  }

  update(runId) {
    this.controller.update(runId);
  }
}

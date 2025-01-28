/**
 * Manages the recipe reduction process including starting, stopping, and updating reduction
 * operations.
 * @param {Object} options - Configuration options for the model.
 * @class
 */
class RecipeReductionModel {
  constructor(options) {
    this.options = options;
    this.api = this.options.api;
    this.recipesUrl = "dragonsrecipes/";
    this.reducesUrl = "dragonsreduce/";
    this._recipeId = null;
    this._currentReduceData = null;
    this.isEditMode = false;
  }

  /**
   * Starts the reduction process for a given set of file IDs associated with a recipe.
   * @param {Array<number>} fileIds - Array of file IDs to be reduced.
   * @returns {Promise<Object>} A promise that resolves to the response from the server.
   * @async
   */
  async startReduce(fileIds) {
    const data = { recipe_id: this.recipeId, file_ids: fileIds };
    try {
      const response = await this.api.post(`${this.reducesUrl}`, data);
      this.currentReduceData = response;
      return response;
    } catch (error) {
      console.error("Error starting reduce:", error);
    }
  }

  /**
   * Stops the reduction process.
   * @param {number} reduceId The ID of the reduction to be stopped.
   * @returns {Promise<Object>} A promise that resolves to the response from the server.
   * @throws {Error} If the API request fails, an error is logged to the console.
   * @async
   */
  async stopReduce() {
    const data = { status: "canceled" };
    if (!this.currentReduceData) return;
    try {
      const response = await this.api.patch(
        `${this.reducesUrl}${this.currentReduceData.id}/`,
        data
      );
      this.reduce = response;
      return response;
    } catch (error) {
      console.error("Error stopping reduce:", error);
    }
  }

  /**
   * Asynchronously fetches help documentation for a specified recipe.
   * @param {string} recipeId The ID of the recipe for which help documentation is being requested.
   * @returns {Promise<Object>} A promise that resolves with the help documentation for the
   * specified recipe.
   * @throws {Error} If the API request fails, an error is logged to the console.
   * @async
   */
  async fetchHelp() {
    try {
      const response = await this.api.get(
        `${this.recipesUrl}${this.recipeId}/?include=help`
      );
      return response;
    } catch (error) {
      console.error("Error fetching recipe help:", error);
    }
  }

  /**
   * Asynchronously updates the function definition of a recipe by sending a PATCH request.
   * @param {number} recipeId The unique identifier of the recipe.
   * @param {string|null} functionDefinition The new function definition to update, or null to
   * reset.
   * @returns {Promise<Object|null>} The updated recipe object if successful, or null if an error
   * occurs.
   */
  async updateFunctionDefinitionAndUparms(functionDefinition = null, uparms = null) {
    const data = { function_definition: functionDefinition, uparms };
    try {
      const response = await this.api.patch(
        `${this.recipesUrl}${this.recipeId}/`,
        data
      );
      return response;
    } catch (error) {
      console.error("Error updating function definition and uparms:", error);
    }
  }

  get currentReduceData() {
    return this._currentReduceData;
  }

  set currentReduceData(value) {
    this._currentReduceData = value;
  }

  get recipeId() {
    return this._recipeId;
  }

  set recipeId(value) {
    this._recipeId = value;
  }
}

class RecipeReductionTemplate {
  constructor(options) {
    this.options = options;
    this.accordionSetups = {
      buttons: {
        recipeAccordion: "Modify Recipe",
        logAccordion: "Log",
      },
      callbacks: {
        recipeAccordion: this._createRecipeAccordionItem.bind(this),
        logAccordion: this._createLogAccordionItem.bind(this),
      },
      classes: {
        recipeAccordion: [],
        logAccordion: ["p-0", "border", "border-top-0", "rounded-bottom"],
      },
    };
  }

  /**
   * Creates the main container for the files table.
   * @param {Array} data - The data used to create the table.
   * @returns {HTMLElement} The container element.
   */
  create(data) {
    const container = this._createContainer();
    const card = this._createCard(data);

    container.appendChild(card);
    return container;
  }

  /**
   * Creates a container element.
   * @returns {HTMLElement} The container element.
   * @private
   */
  _createContainer() {
    // Don't show anything until a recipe is selected.
    const container = Utils.createElement("div", "d-none");
    return container;
  }

  /**
   * Creates a card container.
   * @return {HTMLElement} The card element.
   */
  _createCard(data) {
    const card = Utils.createElement("div", ["card"]);
    card.append(
      this._createCardHeader(data),
      this._createCardBody(data),
      this._createCardFooter1(data),
      this._createCardFooter2(data)
    );

    return card;
  }

  /**
   * Creates the card body.
   * @returns {HTMLElement} The card body.
   */
  _createCardBody() {
    const cardBody = Utils.createElement("div", "card-body");
    return cardBody;
  }

  /**
   * Creates the card header element with action buttons.
   * @param {Object} data - Data necessary for building the header.
   * @returns {HTMLElement} - A populated card header element.
   * @private
   */
  _createCardHeader(data) {
    const cardHeader = Utils.createElement("div", "card-header");
    const row = Utils.createElement("div", ["row"]);
    const col1 = Utils.createElement("div", ["col", "align-self-center"]);
    const col2 = Utils.createElement("div", ["col", "text-end"]);

    // Create content for column 1.
    const p = Utils.createElement("p", ["my-0", "h5"]);
    p.textContent = `${
      this.options.observationTypeToDisplay[data.observation_type.toLowerCase()]
    } Reduction`;
    col1.appendChild(p);

    // Create content for column 2
    const startButton = Utils.createElement("button", ["btn", "btn-success", "me-1"]);
    const stopButton = Utils.createElement("button", ["btn", "btn-danger"]);
    startButton.dataset.action = "startReduce";
    startButton.textContent = "Start";
    stopButton.textContent = "Stop";
    stopButton.dataset.action = "stopReduce";
    stopButton.disabled = false;
    col2.append(startButton, stopButton);

    // Build the layout.
    row.append(col1, col2);

    cardHeader.appendChild(row);
    return cardHeader;
  }

  /**
   * Creates the first footer for the recipe accordion.
   * @param {Object} data - Data necessary for building the footer.
   * @returns {HTMLElement} - A populated card footer element.
   * @private
   */
  _createCardFooter1(data) {
    // Create footer.
    const cardFooter = Utils.createElement("div", "card-footer");
    const recipeAccordion = this._createAccordion("recipeAccordion", data);
    cardFooter.appendChild(recipeAccordion);
    return cardFooter;
  }

  /**
   * Creates the second footer for the recipe accordion, specifically for logging.
   * @param {Object} data - Data necessary for building the footer.
   * @returns {HTMLElement} - A populated card footer element.
   * @private
   */
  _createCardFooter2(data) {
    const cardFooter = Utils.createElement("div", ["card-footer"]);
    const loggerAccordion = this._createAccordion("logAccordion", data);

    cardFooter.appendChild(loggerAccordion);

    return cardFooter;
  }

  /**
   * Creates an accordion component for recipe modification or logging.
   * @param {string} name - The name identifier for the accordion.
   * @param {Object} data - Data to associate with the accordion.
   * @returns {HTMLElement} - A new accordion element.
   * @private
   */
  _createAccordion(name, data) {
    // Set the ID to reference the recipe ID all the recipe belong to.
    const accordionId = this._createId(data, name);
    const accordion = Utils.createElement("div", ["accordion", "accordion-flush"]);
    accordion.id = accordionId;

    const accordionItem = this._createAccordionItem(name, data);

    accordion.appendChild(accordionItem);

    return accordion;
  }

  /**
   * Creates an accordion item element.
   * @param {string} name - Name identifier for the accordion item.
   * @param {Object} data - Data to associate with the accordion item.
   * @returns {HTMLElement} - A new accordion item element.
   * @private
   */
  _createAccordionItem(name, data) {
    // Create IDs to use to link.
    const collapseId = this._createId(data, `${name}Collapse`);
    const accordionHeaderId = this._createId(data, `${name}AccordionHeader`);

    // Create accordion item.
    const accordionItem = Utils.createElement("div", "accordion-item");

    // Create and configure header.
    const accordionHeader = Utils.createElement("h2", "accordion-header");
    accordionHeader.id = accordionHeaderId;

    // Create and configure accordion button.
    const accordionButton = Utils.createElement("button", ["accordion-button"]);
    accordionButton.setAttribute("type", "button");
    accordionButton.setAttribute("data-toggle", "collapse");
    accordionButton.setAttribute("data-target", `#${collapseId}`);
    accordionButton.setAttribute("aria-expanded", "true");
    accordionButton.setAttribute("aria-controls", collapseId);
    accordionButton.textContent = this.accordionSetups.buttons[name];
    accordionHeader.appendChild(accordionButton);
    accordionItem.appendChild(accordionHeader);

    // Create the collaspible body section that will contain recipe.
    const collapse = Utils.createElement("div", [
      "accordion-collapse",
      "collapse",
      "show",
    ]);
    collapse.id = collapseId;
    collapse.setAttribute("aria-labelledby", accordionHeaderId);

    collapse.setAttribute("data-parent", `#${this._createId(data, name)}`);

    const accordionBody = Utils.createElement("div", [
      "accordion-body",
      ...this.accordionSetups.classes[name],
    ]);

    this.accordionSetups.callbacks[name](accordionBody, data);

    collapse.appendChild(accordionBody);
    accordionItem.appendChild(collapse);

    return accordionItem;
  }

  /**
   * Generates a unique ID for an element based on the data and a suffix.
   * @param {Object} data - Data used to generate the ID base.
   * @param {string} suffix - Suffix to append to the ID.
   * @returns {string} - A unique element ID.
   * @private
   */
  _createId(data, suffix) {
    return `recipe${data.id}${suffix}`;
  }

  /**
   * Initializes and returns an editor element.
   * @param {Object} data - Data associated with the editor.
   * @returns {HTMLElement} - An editor element.
   * @private
   */
  _createEditor(data) {
    // Create code viewer.
    const div = Utils.createElement("div", "mb-1");
    div.id = this._createId(data, "Editor");

    return div;
  }

  /**
   * Generates a set of editor buttons for actions such as edit, save, and reset.
   * @returns {HTMLElement} - A div containing configured buttons.
   * @private
   */
  _createEditorButtons() {
    const row = Utils.createElement("div", "row");
    const col1 = Utils.createElement("div", "col");
    const col2 = Utils.createElement("div", ["col", "text-end"]);

    const editOrSaveButton = Utils.createElement("button", [
      "btn",
      "btn-primary",
      "me-1",
    ]);
    editOrSaveButton.textContent = "Edit";
    editOrSaveButton.dataset.action = "editOrSaveRecipe";

    const resetButton = Utils.createElement("button", ["btn", "btn-secondary"]);
    resetButton.textContent = "Reset";
    resetButton.dataset.action = "resetRecipe";

    const helpButton = Utils.createElement("button", ["btn", "btn-link"]);
    helpButton.textContent = "Help";
    helpButton.dataset.action = "helpRecipe";
    helpButton.setAttribute("data-bs-toggle", "offcanvas");
    helpButton.setAttribute("data-bs-target", `#helpOffcanvas`);

    // Build the layout.
    col1.append(editOrSaveButton, resetButton);
    col2.appendChild(helpButton);
    row.append(col1, col2);

    return row;
  }

  /**
   * Appends editor and editor button components to the provided accordion body.
   * @param {HTMLElement} accordionBody The accordion section where the editor and buttons will be appended.
   */
  _createRecipeAccordionItem(accordionBody, data) {
    const uparmsInput = this._createUparms(data);
    const editorDiv = this._createEditor(data);
    const editorButtons = this._createEditorButtons();

    accordionBody.append(uparmsInput, editorDiv, editorButtons);
  }

  /**
   * Creates the user parameters input section as part of an accordion item.
   * This section allows users to input or modify parameters related to the recipe.
   * @param {Object} data - Data associated with the specific recipe, used for setting initial
   * values.
   * @returns {HTMLElement} The user parameters section element.
   * @private
   */
  _createUparms(data) {
    // Create a container.
    const div = Utils.createElement("div", "mb-3");
    const row = Utils.createElement("div", ["row", "g-3"]);
    const labelCol = Utils.createElement("div", ["col-sm-3"]);
    const inputCol = Utils.createElement("div", ["col-sm-9"]);

    // Create a label element.
    const uparmsId = this._createId(data, "Uparms");
    const label = Utils.createElement("label", ["col-form-label"]);
    label.textContent = "Optional Parameters";
    label.htmlFor = uparmsId;

    // Create information popover button with an icon for uparms.
    const infoButton = Utils.createElement("a", ["link-primary", "ms-1"]);
    infoButton.setAttribute("type", "button");
    infoButton.setAttribute("tabindex", "0");
    infoButton.setAttribute("data-bs-trigger", "focus");
    infoButton.setAttribute("data-bs-toggle", "popover");
    infoButton.setAttribute("data-bs-placement", "top");
    infoButton.setAttribute("data-bs-html", "true");
    infoButton.setAttribute("data-bs-title", "Set Parameter Values");
    infoButton.setAttribute(
      "data-bs-content",
      `
    <p>Use this input field to set parameter values for primitives in the recipe.</p>
    <p>Input should be formatted as follows:</p>
    <ul>
    <li><code>[('primitive1_name:parameter1_name', parameter1_value), ('primitive2_name:parameter2_name', parameter2_value)]</code></li>
    <li>If the primitive name is omitted, e.g., <code>('parameter_name', parameter_value)</code>, the parameter value will be applied to all primitives in the recipe that use this parameter.</li>
    </ul>
    <p>While direct modifications to the recipe can be made using the code block below, it is generally recommended to set parameters using this input field for ease and accuracy.<p/>
  `
    );

    // Create icon element.
    const icon = Utils.createElement("i", ["fa-solid", "fa-circle-info"]);
    infoButton.appendChild(icon);

    new bootstrap.Popover(infoButton);

    // Create an input element.
    const input = Utils.createElement("input", ["form-control"]);
    input.type = "text";
    input.id = uparmsId;
    input.placeholder = "[('primitive:parameter', value)]";
    input.value = data.uparms;
    input.disabled = true;
    this.uparms = input;

    // Append the label and input to the container.
    inputCol.appendChild(input);
    labelCol.append(label, infoButton);
    row.append(labelCol, inputCol);
    div.appendChild(row);

    return div;
  }

  /**
   * Creates a log section within an accordion item, used for displaying real-time logs or messages
   * related to the recipe reduction process.
   * @param {HTMLElement} accordionBody - The body of the accordion where the log will be displayed.
   * @param {Object} data - Data associated with the specific recipe, potentially including log
   * entries.
   * @private
   */
  _createLogAccordionItem(accordionBody, data) {
    const div = Utils.createElement("div", ["ps-2"]);
    div.id = this._createId(data, "Logger");
    // this.logger = new Logger(div);

    accordionBody.appendChild(div);
  }
}

/**
 * Represents the view layer for managing the recipe reduction interface.
 * Handles the user interface elements and interactions.
 * @param {Object} template - The template used to render the view.
 * @param {Object} options - Configuration options for the view.
 */
class RecipeReductionView {
  constructor(template, options) {
    this.template = template;
    this.options = options;

    this.container = null;
    this.editor = null;
    this.logger = null;
    this.recipe = null;
    this.progress = null;
    this.stopButton = null;
    this.startButton = null;
    this.editOrSaveButton = null;
    this.resetButton = null;
    this.helpButton = null;
    this.isEditMode = false;
  }

  /**
   * Renders changes to the view based on a specified command.
   * @param {string} viewCmd - The command that specifies the action to perform.
   * @param {Object} parameter - Parameters needed for the rendering action.
   */
  render(viewCmd, parameter) {
    switch (viewCmd) {
      case "create":
        this._create(parameter.parentElement, parameter.data);
        break;
      case "show":
        this._show();
        break;
      case "hide":
        this._hide();
        break;
      case "log":
        this._log(parameter.message);
        break;
      case "enableEditRecipe":
        this._enableEditRecipe();
        break;
      case "disableEdit":
        this._disableEdit();
        break;
      case "updateRecipe":
        this._updateRecipe(parameter.data);
        break;
      case "disableSaveRecipe":
        this._disableSaveRecipe();
        break;
      case "update":
        this._update(parameter.data);
        break;
      case "clearLog":
        this._clearLog();
        break;
      case "startReduce":
        this._startReduce(parameter.data);
        break;
      case "stopReduce":
        this._stopReduce(parameter.data);
        break;
    }
  }
  _startReduce(data) {
    this.startButton.disabled = true;
    this.stopButton.disabled = false;
    if (!data) return;
    this._update(data);
  }

  _stopReduce(data) {
    this.startButton.disabled = false;
    // To let multiple cancels if the first fails.
    this.stopButton.disabled = false;
    if (!data) return;
    this._update(data);
  }

  _clearLog() {
    this.logger.clear();
  }

  _update(data) {
    // TODO: Update button state depending on status.
    this.progress.update(data.status);
    if (["canceled", "done", "error"].includes(data.status)) {
      this.startButton.disabled = false;
      this.stopButton.disabled = false;
    } else {
      this.startButton.disabled = true;
      this.stopButton.disabled = false;
    }
  }

  /**
   * Updates the recipe editor with new data.
   * @param {Object} data - Data containing the recipe details.
   * @private
   */
  _updateRecipe(data) {
    this.editor.setValue(data.active_function_definition, -1);
    this.uparmsInput.value = data.uparms;
  }

  /**
   * Enables editing mode in the recipe editor.
   * @private
   */
  _enableEditRecipe() {
    this.editor.setReadOnly(false);
    this.editOrSaveButton.textContent = "Save";
    this.editor.container.classList.remove("editor-disabled");
    this.uparmsInput.disabled = false;
  }

  /**
   * Disables editing mode in the recipe editor, locking changes.
   * @private
   */
  _disableSaveRecipe() {
    this.editor.setReadOnly(true);
    this.editOrSaveButton.textContent = "Edit";
    this.editor.container.classList.add("editor-disabled");
    this.uparmsInput.disabled = true;
  }

  /**
   * Logs a message to the recipe log interface.
   * @param {string} message - The message to log.
   * @private
   */
  _log(message) {
    this.logger.log(message);
  }

  /**
   * Shows the recipe reduction interface.
   * @private
   */
  _show() {
    this.container.classList.remove("d-none");
  }

  /**
   * Hides the recipe reduction interface.
   * @private
   */
  _hide() {
    this.container.classList.add("d-none");
  }

  /**
   * Creates the initial setup for the recipe reduction interface.
   * @param {HTMLElement} parentElement - The parent element to which the view will be attached.
   * @param {Object} data - The data needed to construct the view.
   * @private
   */
  _create(parentElement, data) {
    this.container = this.template.create(data);

    // Append and build rest of things here.
    this.editor = this._createEditor(data);
    this._updateEditorTheme();
    this.logger = new Logger(this.container.querySelector(`#recipe${data.id}Logger`));
    this.progress = new Progress(this.container.querySelector(".card-body"));
    this.stopButton = this.container.querySelector('[data-action="stopReduce"]');
    this.startButton = this.container.querySelector('[data-action="startReduce"]');
    this.editOrSaveButton = this.container.querySelector(
      '[data-action="editOrSaveRecipe"]'
    );
    this.resetButton = this.container.querySelector('[data-action="resetRecipe"]');
    this.helpButton = this.container.querySelector('[data-action="helpRecipe"]');
    this.uparmsInput = this.container.querySelector(`#recipe${data.id}Uparms`);
    this.parentElement = parentElement;
    this.parentElement.appendChild(this.container);
  }

  /**
   * Initializes and configures the Ace editor within the view.
   * @param {Object} data - The data used to configure the editor.
   * @returns {Object} - The initialized Ace editor instance.
   * @private
   */
  _createEditor(data) {
    const editorDiv = this.container.querySelector(`#recipe${data.id}Editor`);
    const editor = ace.edit(null);

    // Move cursor back to start with -1.
    editor.setValue(data.active_function_definition, -1);
    editor.session.setMode("ace/mode/python");

    editor.container.style.height = "100%";
    editor.container.style.width = "100%";
    editor.container.style.minHeight = "300px";
    editor.container.classList.add("editor-disabled");
    editor.setReadOnly(true);

    editorDiv.appendChild(editor.container);

    return editor;
  }

  /**
   * Updates the theme of the editor based on user settings.
   * @private
   */
  _updateEditorTheme() {
    const storedTheme = localStorage.getItem("theme");
    const theme =
      storedTheme === "dark"
        ? this.options.editor_themes.dark
        : this.options.editor_themes.light;
    this.editor.setTheme(theme);
  }

  /**
   * Binds UI event callbacks to the view elements based on specified events.
   * @param {string} event - The name of the event to bind.
   * @param {Function} handler - The handler function to execute on the event.
   */
  bindCallback(event, handler) {
    switch (event) {
      case "stopReduce":
        Utils.on(this.stopButton, "click", (e) => {
          handler();
        });
        break;
      case "startReduce":
        Utils.on(this.startButton, "click", () => {
          handler();
        });
        break;
      case "editOrSaveRecipe":
        Utils.on(this.editOrSaveButton, "click", () => {
          handler({
            uparms: this.uparmsInput.value,
            functionDefinition: this.editor.getValue(),
          });
        });
        break;
      case "resetRecipe":
        Utils.on(this.resetButton, "click", () => {
          handler();
        });
        break;
      case "helpRecipe":
        Utils.on(this.helpButton, "click", () => {
          handler();
        });
        break;
    }
  }
}

/**
 * Manages interactions between the model and view in the recipe reduction context.
 * @param {Object} model - The data model for the recipe reduction.
 * @param {Object} view - The view layer for user interaction.
 * @param {Object} options - Configuration options for the controller.
 */
class RecipeReductionController {
  constructor(model, view, options) {
    this.model = model;
    this.view = view;
    this.options = options;
  }

  /**
   * Initializes the view and model for a new recipe reduction.
   * @param {HTMLElement} parentElement - The container where the component should be rendered.
   * @param {Object} data - Data needed to render the component.
   */
  create(parentElement, data) {
    this.model.recipeId = data.id;
    this.model.identifier = new Identifier(
      null, // No run ID.
      data.observation_type,
      data.observation_class,
      data.object_name
    );
    this.view.render("create", { parentElement, data });
    this._bindCallbacks();
  }

  /**
   * Binds event handlers to view events.
   * @private
   */
  _bindCallbacks() {
    this.view.bindCallback("stopReduce", () => this._stopReduce());
    this.view.bindCallback("startReduce", () => this._startReduce());
    this.view.bindCallback("editOrSaveRecipe", (item) =>
      this._editOrSaveRecipe(item.uparms, item.functionDefinition)
    );
    this.view.bindCallback("resetRecipe", () => this._resetRecipe());
    this.view.bindCallback("helpRecipe", () => this._helpRecipe());
  }

  /**
   * Starts the reduction process via the model.
   * @private
   */
  async _startReduce() {
    this.view.render("clearLog");
    // TODO: Get all files to send from the associated table.
    const tbody = document.querySelector(
      `#${this.model.identifier.idPrefix}FilesTable tbody`
    );
    // Directly retrieve file IDs from checked checkboxes.
    const fileIds = Array.from(
      tbody.querySelectorAll("input[type='checkbox']:checked")
    ).map((input) => input.closest("tr").dataset.fileId);

    const data = await this.model.startReduce(fileIds);
    this.view.render("startReduce", { data });
  }

  /**
   * Handles the logic for editing or saving recipe details.
   * @param {string} uparms - Updated parameters for the recipe.
   * @param {string} functionDefinition - Updated function definition for the recipe.
   * @private
   */
  async _editOrSaveRecipe(uparms, functionDefinition) {
    this.model.isEditMode = !this.model.isEditMode;
    if (this.model.isEditMode) {
      this.view.render("enableEditRecipe");
    } else {
      this.view.render("disableSaveRecipe");
      const data = await this.model.updateFunctionDefinitionAndUparms(
        functionDefinition,
        uparms
      );
      this.view.render("updateRecipe", { data });
    }
  }

  /**
   * Resets the recipe details to their default state.
   * @private
   */
  async _resetRecipe() {
    const data = await this.model.updateFunctionDefinitionAndUparms();
    this.view.render("updateRecipe", { data });
  }

  /**
   * Logs a message related to the recipe reduction process.
   * @param {string} message - The message to log.
   * @private
   */
  log(message) {
    this.view.render("log", { message });
  }

  update(data) {
    // Update the model with new information.
    this.model.currentReduceData = { id: data.reduce_id };
    this.view.render("update", { data });
  }

  /**
   * Fetches and displays help documentation for the current recipe.
   * @private
   */
  async _helpRecipe() {
    // Clear and show loading bar since it is not hidden.
    window.helpOffcanvas.clearTitleAndContent();
    window.helpOffcanvas.isLoading();

    // Pass in the recipe to get the help for it.
    const data = await this.model.fetchHelp();
    window.helpOffcanvas.updateAndShowPrimitivesDocumentation(data);
  }

  /**
   * Stops the reduction process.
   * @private
   */
  async _stopReduce() {
    const data = await this.model.stopReduce();
    this.view.render("stopReduce", { data });
  }

  /**
   * Makes the recipe reduction interface visible.
   */
  show() {
    this.view.render("show");
  }

  /**
   * Hides the recipe reduction interface.
   */
  hide() {
    this.view.render("hide");
  }
}

/**
 * Main class for managing the recipe reduction component, integrating model, view, and controller layers.
 * @param {HTMLElement} parentElement - The parent element to append the component to.
 * @param {string} runId - A unique identifier for the run associated with the recipe reduction.
 * @param {Object} data - Data necessary for initializing the component.
 * @param {Object} [options={}] - Optional configuration options for the recipe reduction.
 */
class RecipeReduction {
  static #defaultOptions = {
    id: "RecipeReduction",
    observationTypeToDisplay: {
      bias: "Bias",
      flat: "Flat",
      dark: "Dark",
      arc: "Arc",
      pinhole: "Pinhole",
      ronchi: "Ronchi",
      fringe: "Fringe",
      bpm: "BPM",
      standard: "Standard",
      object: "Science",
      other: "Error",
    },
    editor_themes: {
      dark: "ace/theme/cloud9_night",
      light: "ace/theme/dawn",
    },
  };

  constructor(parentElement, data, options = {}) {
    this.options = {
      ...RecipeReduction.#defaultOptions,
      ...options,
      api: window.api,
    };
    const model = new RecipeReductionModel(this.options);
    const template = new RecipeReductionTemplate(this.options);
    const view = new RecipeReductionView(template, this.options);
    this.controller = new RecipeReductionController(model, view, this.options);

    this._init(parentElement, data);
  }

  /**
   * Initializes the component by creating its MVC structure and rendering it.
   * @param {HTMLElement} parentElement - The container where the component will be mounted.
   * @param {string} runId - The run identifier for which the component is created.
   * @param {Object} data - Initialization data for the component.
   * @private
   */
  _init(parentElement, data) {
    this._create(parentElement, data);
  }

  /**
   * Creates the MVC components and attaches them to the parent element.
   * @param {HTMLElement} parentElement - The parent element to attach the component to.
   * @param {Object} data - Data needed for the creation.
   * @private
   */
  _create(parentElement, data) {
    this.controller.create(parentElement, data);
  }

  /**
   * Makes the component visible.
   */
  show() {
    this.controller.show();
  }

  /**
   * Hides the component.
   */
  hide() {
    this.controller.hide();
  }

  update(data) {
    this.controller.update(data);
  }

  log(message) {
    this.controller.log(message);
  }
}

/**
 * Class to generate HTML templates.
 * @param {Object} options - Configuration options for the template.
 */
class RunSetupTemplate {
  constructor(options) {
    this.options = options;
  }

  /**
   * Creates the main container for the run setup.
   * @returns {HTMLElement} The container element with the card inside.
   */
  create() {
    const container = this._createContainer();
    const card = this._createCard();
    card.append(this._createCardHeader(), this._createCardBody());
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
   * Creates the header section of the card.
   * @returns {HTMLElement} The card header element
   */
  _createCardHeader() {
    const div = Utils.createElement("div", ["card-header", "h5", "mb-0"]);
    div.textContent = "Setup and Manage Reduction Runs";

    return div;
  }

  /**
   * Creates a card container.
   * @returns {HTMLElement} The card element.
   * @private
   */
  _createCard() {
    const card = Utils.createElement("div", ["card"]);

    return card;
  }

  /**
   * Creates the body section of the card.
   * @returns {HTMLElement} The card body element.
   * @private
   */
  _createCardBody() {
    const cardBody = Utils.createElement("div", ["card-body"]);
    cardBody.append(
      this._createRunTypeSelection(),
      this._createSetupForm(),
      this._createRunSelect(),
      this._createLoadingDiv()
    );
    return cardBody;
  }

  /**
   * Creates a select option element for the run.
   * @param {Object} data - The data object containing run information.
   * @returns {HTMLOptionElement} The option element for the run select.
   */
  createRunSelectOption(data) {
    const option = Utils.createElement("option");
    option.value = data.id;
    option.textContent = data.run_id;

    return option;
  }

  /**
   * Creates a selection for choosing the run type with buttons.
   * @returns {HTMLElement} The run type selection element.
   * @private
   */
  _createRunTypeSelection() {
    const row = Utils.createElement("div", ["row", "g-3", "mb-3"]);
    const col = Utils.createElement("div", ["col-12"]);

    const btnGroup = Utils.createElement("div", ["btn-group", "d-flex"]);
    btnGroup.setAttribute("role", "group");
    btnGroup.setAttribute("aria-label", "Run Type Options");

    const existingRunInput = Utils.createElement("input", ["btn-check"]);
    existingRunInput.type = "radio";
    existingRunInput.name = "runRadio";
    existingRunInput.id = `existingRunRadio${this.options.id}`;
    existingRunInput.autocomplete = "off";
    existingRunInput.checked = true;
    existingRunInput.dataset.action = "existing";

    const existingRunLabel = Utils.createElement("label", [
      "btn",
      "btn-outline-primary",
    ]);
    existingRunLabel.setAttribute("for", existingRunInput.id);
    existingRunLabel.textContent = "Existing Run";

    const newRunInput = Utils.createElement("input", ["btn-check"]);
    newRunInput.type = "radio";
    newRunInput.name = "runRadio";
    newRunInput.id = `newRunRadio${this.options.id}`;
    newRunInput.autocomplete = "off";
    newRunInput.dataset.action = "new";

    const newRunLabel = Utils.createElement("label", ["btn", "btn-outline-primary"]);
    newRunLabel.setAttribute("for", newRunInput.id);
    newRunLabel.textContent = "New Run";

    btnGroup.append(existingRunInput, existingRunLabel, newRunInput, newRunLabel);
    col.append(btnGroup);
    row.append(col);

    return row;
  }

  /**
   * Creates the setup form for new runs.
   * @returns {HTMLElement} The setup form element.
   * @private
   */
  _createSetupForm() {
    const fieldConfigs = [
      {
        type: "text",
        id: "formRunID",
        name: "run_id",
        label: "Run ID",
        placeholder: "Default: run-YYYYMMDDhhmmss",
      },
      {
        type: "text",
        id: "formConfigFilename",
        name: "config_filename",
        label: "Configuration File",
        placeholder: "Default: dragonsrc",
      },
      {
        type: "text",
        id: "formCalManagerFilename",
        name: "cal_manager_filename",
        label: "Calibration Manager File",
        placeholder: "Default: cal_manager.db",
      },
    ];
    const form = Utils.createElement("form", ["d-none", "mb-3"]);
    form.id = `form${this.options.id}`;
    form.method = "post";

    const row = Utils.createElement("div", ["row", "g-3"]);
    fieldConfigs.forEach((config) => {
      const col = this._createFormInputCol(config);
      row.appendChild(col);
    });

    const submitButton = Utils.createElement("button", [
      "btn",
      "btn-primary",
      "d-block",
      "w-100",
    ]);
    submitButton.type = "submit";
    submitButton.textContent = "Create Run";

    const submitCol = Utils.createElement("div", ["col-12"]);
    submitCol.append(submitButton);

    row.appendChild(submitCol);
    form.append(row);

    return form;
  }

  /**
   * Creates a column containing a form input field.
   * @param {Object} config - Configuration for the input field.
   * @returns {HTMLElement} The column element containing the input field and label.
   * @private
   */
  _createFormInputCol(config) {
    const col = Utils.createElement("div", ["col-12"]);

    const label = Utils.createElement("label", ["form-label"]);
    label.setAttribute("for", `${config.id}${this.options.id}`);
    label.textContent = config.label;

    const input = this._createFormInput(config);

    col.appendChild(label);
    col.appendChild(input);

    return col;
  }

  /**
   * Creates an input element based on provided configuration.
   * @param {Object} config - Configuration for the input field.
   * @return {HTMLElement} The input element.
   * @private
   */
  _createFormInput(config) {
    const input = Utils.createElement("input", ["form-control"]);
    input.type = config.type;
    input.id = `${config.id}${this.options.id}`;
    input.name = config.name;
    if (config.placeholder) input.placeholder = config.placeholder;
    if (config.value) input.value = config.value;

    return input;
  }

  /**
   * Creates the run selection dropdown and the table for displaying runs.
   * @returns {HTMLElement} The element containing the run selection and table.
   * @private
   */
  _createRunSelect() {
    const container = this._createContainer();
    container.id = `runSelectContainer${this.options.id}`;
    const row = Utils.createElement("div", ["row", "g-3"]);
    const col = Utils.createElement("div", "col-12");

    const inputGroup = Utils.createElement("div", ["input-group"]);
    const select = Utils.createElement("select", ["form-select"]);
    select.id = `runSelect${this.options.id}`;
    select.innerHTML = `<option value="" selected hidden>Select A Run</option>`;

    const deleteButton = Utils.createElement("button", ["btn", "btn-danger"]);
    deleteButton.setAttribute("type", "button");
    deleteButton.dataset.action = "deleteRun";
    deleteButton.textContent = "Delete";
    deleteButton.disabled = true;

    inputGroup.append(select, deleteButton);
    col.appendChild(inputGroup);

    // Create run table row to append to.
    const tableCol = Utils.createElement("div", "col-12");
    tableCol.id = `runTable${this.options.id}`;
    row.append(col, tableCol);
    container.appendChild(row);

    return container;
  }

  /**
   * Creates a loading indicator element.
   * @return {HTMLElement} The loading div element with a spinner.
   * @private
   */
  _createLoadingDiv() {
    const div = Utils.createElement("div", ["d-none", "text-center"]);
    div.id = `loading${this.options.id}`;
    const spinner = Utils.createElement("div", ["spinner-border", "text-secondary"]);
    const spinnerInner = Utils.createElement("span", ["visually-hidden"]);
    spinnerInner.textContent = "Loading ...";
    const spinnerText = Utils.createElement("p");
    spinnerText.textContent = "Building run, please wait...";

    spinner.appendChild(spinnerInner);
    div.append(spinner, spinnerText);

    return div;
  }
}

/**
 * Class representing the model for setting up and managing run data.
 * @param {number} observationRecordId - The ID of the observation record.
 * @param {Object} api - The API object for making requests.
 */
class RunSetupModel {
  constructor(observationRecordId, options) {
    this._observationRecordId = observationRecordId;
    this.options = options;
    this.api = this.options.api;
    this._rawData = {};
    this._data = [];
    this.url = "dragonsruns/";
  }

  get observationRecordId() {
    return this._observationRecordId;
  }

  set runId(value) {
    this._runId = parseInt(value);
  }

  get runId() {
    return this._runId;
  }

  set data(value) {
    this._rawData = value;
    this._data = value.results;
  }

  get data() {
    return this._data;
  }

  get rawData() {
    return this._rawData;
  }

  /**
   * Clears the stored run data.
   */
  clearData() {
    this._rawData = {};
    this._data = [];
  }

  /**
   * Gets the run data for the current run ID.
   * @returns {Object} The run data for the current run ID or an empty object if not found.
   */
  getRunData() {
    return this.data.find((run) => run.id === this.runId);
  }

  /**
   * Fetches a list of runs associated with a specific observation record.
   * @async
   * @returns {Promise<Array>} A promise that resolves to an array of runs.
   * @throws {Error} Throws an error if the fetch operation fails.
   */
  async fetchRuns() {
    try {
      const response = await this.api.get(
        `${this.url}?observation_record=${this._observationRecordId}`
      );
      this.data = response;
    } catch (error) {
      console.error("Error fetching runs:", error);
    }
  }

  /**
   * Submits a new run to the API using form data.
   * @async
   * @param {FormData} formData - The form data containing run information.
   * @returns {Promise<void>} A promise that resolves when the form submission is complete.
   * @throws {Error} Throws an error if the form submission fails.
   */
  async submitForm(formData) {
    try {
      // Don't stringify the form.
      await this.api.post(
        `${this.url}?observation_record=${this._observationRecordId}`,
        formData,
        {},
        false
      );
    } catch (error) {
      console.error("Error initializing DRAGONS run:", error);
      throw error;
    }
  }

  /**
   * Deletes the current DRAGONS run by its ID using the API.
   *
   * @async
   * @throws {Error} - Throws an error if the delete request fails.
   * @returns {Promise<void>} - Resolves when the run is successfully deleted.
   */
  async deleteRun() {
    try {
      await this.api.delete(`${this.url}${this.runId}`);
    } catch (error) {
      console.error(`Error deleting DRAGONS run ID: ${this.runId}`);
      throw error;
    }
  }
}

/**
 * Class representing the view for setting up and managing run data in the UI.
 * @param {Object} template - The template used for rendering the view elements.
 * @param {HTMLElement} parentElement - The DOM element to which the view will be appended.
 * @param {Object} options - Configuration options for the view.
 */
class RunSetupView {
  constructor(template, parentElement, options) {
    this.template = template;
    this.parentElement = parentElement;
    this.options = options;

    // Create the container.
    this.container = this._create();

    // Grab the important elements
    this.runSelectContainer = this.container.querySelector(
      `#runSelectContainer${this.options.id}`
    );
    this.runSelect = this.container.querySelector(`#runSelect${this.options.id}`);
    this.form = this.container.querySelector(`#form${this.options.id}`);
    this.runTypeExistingRadio = this.container.querySelector(
      `#existingRunRadio${this.options.id}`
    );
    this.runTypeNewRadio = this.container.querySelector(
      `#newRunRadio${this.options.id}`
    );
    this.loadingDiv = this.container.querySelector(`#loading${this.options.id}`);
    this.runTable = new RunTable(
      this.container.querySelector(`#runTable${this.options.id}`)
    );
    this.deleteButton = this.container.querySelector('[data-action="deleteRun"]');
    this.parentElement.appendChild(this.container);

    // Bind the renders and callbacks.
    this.render = this.render.bind(this);
    this.bindCallback = this.bindCallback.bind(this);
    this.bindGlobalCallback = this.bindGlobalCallback.bind(this);
  }

  /**
   * Creates and returns the container for the view elements.
   * @returns {HTMLElement} The container element.
   * @private
   */
  _create() {
    const container = this.template.create();
    return container;
  }

  /**
   * Updates the run selection dropdown with new options.
   * Removes old options except for the first one and adds new ones based on the provided data.
   * @param {Array<Object>} runs - Array of run objects to populate the dropdown.
   * @private
   */
  _updateRunSelect(runs) {
    while (this.runSelect.options.length > 1) {
      this.runSelect.remove(1);
    }

    runs.forEach((run) => {
      this.runSelect.appendChild(this.template.createRunSelectOption(run));
    });
  }

  /**
   * Shows the loading state by hiding the form and run select, showing the loading indicator, and hiding the run table.
   * @private
   */
  _loading() {
    this._setLoading(true);
  }

  /**
   * Hides the loading state by showing the form and run select, hiding the loading indicator, and showing the run table.
   * @private
   */
  _loaded() {
    this._setLoading(false);
  }

  /**
   * Toggles the loading state of the view.
   * @param {boolean} isLoading - Whether to show the loading state or not.
   * @private
   */
  _setLoading(isLoading) {
    // Always want to go back to the existing view.
    this.form.classList.toggle("d-none", true);
    this.runSelectContainer.classList.toggle("d-none", isLoading);
    isLoading ? this.runTable.hide() : this.runTable.show();
    this.loadingDiv.classList.toggle("d-none", !isLoading);
    this.runTypeNewRadio.disabled = isLoading;
    this.runTypeExistingRadio.disabled = isLoading;
  }

  /**
   * Toggles the visibility of the new run form and the run select dropdown.
   * @param {boolean} isVisible - Whether to show the new run form or the run select dropdown.
   * @private
   */
  _setNewFormVisibility(isVisible) {
    this.form.classList.toggle("d-none", !isVisible);
    this.runSelectContainer.classList.toggle("d-none", isVisible);
    // this.runSelect.classList.toggle("d-none", isVisible);
    isVisible ? this.runTable.hide() : this.runTable.show();
  }

  /**
   * Resets the new run form to its initial state.
   * @private
   */
  _resetForm() {
    this.form.reset();
  }

  /**
   * Updates the run table with data.
   * @param {Object} data - payload of data to update with.
   * @private
   */
  _updateRunTable(data) {
    // Need to enable the button to delete.
    this.deleteButton.disabled = false;
    this.runTable.update(data);
  }

  /**
   * Resets the run table.
   * @private
   */
  _resetRunTable() {
    // Need to disable delete button again.
    this.deleteButton.disabled = true;
    this.runTable.reset();
  }

  _deleteRun() {
    // Logic here needs to reset everything to default.
  }

  /**
   * Renders the view based on the given command and parameters.
   * @param {string} viewCmd - The command to render (e.g., "loading", "loaded", "update").
   * @param {Object} [parameter] - Additional parameters to use during rendering.
   */
  render(viewCmd, parameter) {
    switch (viewCmd) {
      case "loading":
        this._loading();
        break;
      case "loaded":
        this._loaded();
        this.runTypeExistingRadio.checked = true;
        break;
      case "update":
        this._updateRunSelect(parameter.data);
        break;
      case "showExistingRuns":
        this._setNewFormVisibility(false);
        break;
      case "showNewRunForm":
        this._setNewFormVisibility(true);
        break;
      case "resetForm":
        this._resetForm();
        break;
      case "updateRunTable":
        this._updateRunTable(parameter.data);
        break;
      case "resetRunTable":
        this._resetRunTable();
        break;
      case "deleteRun":
        this._deleteRun();
        break;
    }
  }

  /**
   * Binds callback functions to the appropriate UI events.
   * @param {string} event - The event name to bind (e.g., "showNewRunForm").
   * @param {Function} handler - The callback function to bind to the event.
   */
  bindCallback(event, handler) {
    switch (event) {
      case "showExistingRuns":
        Utils.on(this.runTypeExistingRadio, "change", (e) => {
          if (e.target.checked) {
            handler();
          }
        });
        break;
      case "showNewRunForm":
        Utils.on(this.runTypeNewRadio, "change", (e) => {
          if (e.target.checked) {
            handler();
          }
        });
        break;
      case "submitNewRunForm":
        Utils.on(this.form, "submit", (e) => {
          e.preventDefault();
          const formData = new FormData(this.form);
          handler({ formData });
        });
        break;
      case "selectRun":
        Utils.on(this.runSelect, "change", (e) => {
          handler({ runId: e.target.value });
        });
        break;
      case "deleteRun":
        Utils.on(this.deleteButton, "click", () => {
          handler();
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
      case "updateRun":
        document.addEventListener("updateRun", (e) => {
          const runId = e.detail.runId;
          handler({ runId });
        });
        break;
    }
  }
}

/**
 * Class representing the controller for the Run Setup.
 * @param {Object} model - The model containing the run data and logic.
 * @param {Object} view - The view for displaying and interacting with the run setup UI.
 */
class RunSetupController {
  constructor(model, view, options) {
    this.model = model;
    this.view = view;
    this.options = options;

    // Bind the callbacks.
    this.view.bindCallback("showNewRunForm", () => this.showNewRunForm());
    this.view.bindCallback("showExistingRuns", () => this.showExistingRuns());
    this.view.bindCallback("submitNewRunForm", (item) =>
      this.submitNewRunForm(item.formData)
    );
    this.view.bindCallback("selectRun", (item) => this._selectRun(item.runId));
    this.view.bindCallback("deleteRun", () => this._deleteRun());
    this.view.bindGlobalCallback("updateRun", (item) => this._updateRun(item.runId));
  }

  /**
   * Initializes the controller by fetching the runs from the model
   * and updating the view with the retrieved data.
   * @async
   * @returns {Promise<void>} A promise that resolves when initialization is complete.
   */
  async init() {
    await this.model.fetchRuns();
    this.view.render("update", { data: this.model.data });
  }

  /**
   * Deletes the current DRAGONS run if a run ID is set.
   *
   * @async
   * @returns {Promise<void>} - Resolves after the run is successfully deleted and the view is updated.
   */
  async _deleteRun() {
    if (!this.model.runId) {
      return;
    }
    try {
      await this.model.deleteRun();
      window.location.reload();
    } catch (error) {
      console.error("Error deleting the run:", error)
    }
    // FIXME: Refreshing the page is just a quick hack to reset everything, this should
    // be better when there is time to properly handle deleting a run.
    // this.view.render("deleteRun");
  }

  /**
   * Updates the run data in the model and refreshes the view with the new run data.
   * @param {string} runId - The new run identifier to update the model with.
   */
  _updateRun(runId) {
    this.model.runId = runId;
    const data = this.model.getRunData();
    this.view.render("updateRunTable", { data });
  }

  /**
   * Submits the new run form, triggers loading state in the view,
   * and after the submission, fetches and updates the runs in the view.
   * @async
   * @param {FormData} formData - The form data containing new run information.
   * @returns {Promise<void>} A promise that resolves when form submission and data update are complete.
   */
  async submitNewRunForm(formData) {
    formData.append("observation_record", this.model.observationRecordId);
    this.view.render("loading");
    await Utils.ensureMinimumDuration(await this.model.submitForm(formData));
    await this.model.fetchRuns();
    this.view.render("update", { data: this.model.data });
    this.view.render("resetForm");
    this.view.render("resetRunTable");
    this.view.render("loaded");
  }

  _selectRun(runId) {
    const event = new CustomEvent("updateRun", {
      detail: { runId },
    });
    // Dispatch the event globally on the document.
    document.dispatchEvent(event);
  }

  /**
   * Shows the existing runs by rendering the appropriate view.
   */
  showExistingRuns() {
    this.view.render("showExistingRuns");
  }

  /**
   * Displays the form for creating a new run by updating the view.
   */
  showNewRunForm() {
    this.view.render("showNewRunForm");
  }
}

/**
 * Class representing the Run Setup component.
 * This class is responsible for initializing and managing the creation or selection of runs
 * in the application. It provides an interface to handle user interaction, fetch run data,
 * and display the appropriate forms and tables for the run setup process.
 * @param {number} observationRecordId - The ID of the observation record associated with the runs.
 * @param {HTMLElement} parentElement - The DOM element where the run setup UI will be rendered.
 * @param {Object} api - The API object used for fetching and submitting run data.
 * @param {Object} [options={}] - Optional configuration options for customizing the run setup.
 */
class RunSetup {
  static #defaultOptions = {
    id: "Run",
  };

  constructor(observationRecordId, parentElement, api, options = {}) {
    this.options = { ...RunSetup.#defaultOptions, ...options, api: window.api };
    this.model = new RunSetupModel(observationRecordId, this.options);
    this.template = new RunSetupTemplate(this.options);
    this.view = new RunSetupView(this.template, parentElement, this.options);
    this.controller = new RunSetupController(this.model, this.view, this.options);
  }

  /**
   * Initializes the run setup by fetching existing runs and rendering the UI.
   * This method should be called to start the run setup process.
   * @async
   * @returns {Promise<void>} A promise that resolves when the initialization process is complete.
   */
  async init() {
    await this.controller.init();
  }
}

/**
 * Creates DOM snippets for the GPP UI.
 * @class
 */
class GPPTemplate {
  #options;

  constructor(options) {
    this.#options = options;
  }

  /**
   * Build the top-level widget DOM.
   * @returns {!HTMLElement} Root container to be appended by the caller.
   */
  create() {
    const container = this.#createContainer();
    const row = Utils.createElement("div", ["row", "g-3"]);

    const col1 = Utils.createElement("div", ["col-sm-6"]);
    col1.append(
      this.#createSelect("program", "Available Programs", "Choose a program...")
    );

    const col2 = Utils.createElement("div", ["col-sm-6"]);
    const observationSelect = this.#createSelect(
      "observation",
      "Available Observations",
      "Choose an observation..."
    );
    col2.append(observationSelect);

    row.append(col1, col2);
    container.append(row);

    return container;
  }

  /**
   * Create an `<option>` element for a `<select>`.
   * @param {{id:string,name:string}} data Program or observation metadata.
   * @returns {!HTMLOptionElement}
   */
  createSelectOption(data) {
    const option = Utils.createElement("option");
    option.value = data.id;
    option.textContent = `${data.id} - ${data.name ?? data.title}`;

    return option;
  }

  /**
   * Creates a container element.
   * @returns {HTMLElement} The container element.
   * @private
   */
  #createContainer() {
    const container = Utils.createElement("div");
    return container;
  }

  /**
   * Generates a `<select>` populated with a hidden placeholder option.
   * @param {string} id  Prefix for the element ID.
   * @param {string} labelText The text for the label.
   * @param {string} optionHint  Placeholder text.
   * @returns {!HTMLSelectElement}
   * @private
   */
  #createSelect(id, labelText, optionHint) {
    const label = Utils.createElement("label", ["form-label"]);
    label.htmlFor = `${id}Select`;
    label.textContent = labelText;
    const select = Utils.createElement("select", ["form-select"]);
    select.id = `${id}Select`;
    select.innerHTML = `<option value="" selected hidden>${optionHint}</option>`;

    if (id === "observation") {
      select.disabled = true;
    }

    const wrapper = Utils.createElement("div");
    wrapper.append(label, select);

    return wrapper;
  }
}

/**
 * Handles remote I/O and caches the results.
 * @class
 */
class GPPModel {
  #options;
  #api;
  // Url specific variables.
  #baseUrl = "gpp/";
  #programsUrl = `${this.#baseUrl}programs/`;
  #observationsUrl = `${this.#baseUrl}observations/`;

  // Data-storing maps.
  #observations = new Map();
  #programs = new Map();

  constructor(options) {
    this.#options = options;
    this.#api = this.#options.api;
  }

  /** Clears every cached observation. */
  clearObservations() {
    this.#observations.clear();
  }

  /** Clears every cached program. */
  clearPrograms() {
    this.#programs.clear();
  }

  /** Clears all cached entities (programs + observations). */
  clear() {
    this.clearPrograms();
    this.clearObservations();
  }

  /**
   * Fetches all programs from the server and refreshes the cache.
   *
   * @async
   * @returns {Promise<void>}
   */
  async fetchPrograms() {
    this.clearPrograms();
    try {
      const response = await this.#api.get(this.#programsUrl);

      // Fill / refresh the Map.
      const programs = response.matches;

      for (const program of programs) {
        this.#programs.set(program.id, program);
      }
    } catch (error) {
      console.error("Error fetching programs:", error);
    }
  }

  /**
   * Fetch all observations for the given program ID and refresh the cache.
   * @async
   * @param {string} programId  Program identifier (e.g. "GN-2025A-Q-101").
   * @returns {Promise<void>}
   */
  async fetchObservations(programId) {
    this.clearObservations();
    try {
      const response = await this.#api.get(
        `${this.#observationsUrl}?program_id=${programId}`
      );

      // Fill / refresh the Map.
      const observations = response.matches;

      for (const observation of observations) {
        this.#observations.set(observation.id, observation);
      }
    } catch (error) {
      console.error("Error fetching observations:", error);
    }
  }

  /**
   * Get an observation object that is already in the cache.
   * @param {string} observationId
   * @returns {Object|undefined}
   */
  getObservation(observationId) {
    return this.#observations.get(observationId);
  }

  /**
   * All cached observations as an array.
   * @type {!Array<!Object>}
   */
  get observationsList() {
    return Array.from(this.#observations.values());
  }

  /**
   * All cached observation IDs.
   * @type {!Array<string>}
   */
  get observationsIds() {
    return Array.from(this.#observations.keys());
  }

  /**
   * Look up a single program by its ID.
   * @param {string} programId
   * @returns {Object|undefined} The program, or `undefined` if not cached.
   */
  getProgram(programId) {
    return this.#programs.get(programId);
  }

  /**
   * All cached programs as an array.
   * @returns {!Array<!Object>}
   */
  get programsList() {
    return Array.from(this.#programs.values());
  }

  /**
   * All cached program IDs.
   * @returns {!Array<string>}
   */
  get programsIds() {
    return Array.from(this.#programs.keys());
  }
}

/**
 * View layer: owns the DOM subtree for the GPP widget and exposes
 * methods the controller can call (`render`, `bindCallback`).
 *
 * @class
 */
class GPPView {
  #options;
  #template;
  #container;
  #parentElement;
  #programSelect;
  #observationSelect;

  /**
   * Construct the view, inject the template, and attach it to the DOM.
   * @param {GPPTemplate} template
   * @param {HTMLElement} parentElement
   * @param {Object} options
   */
  constructor(template, parentElement, options) {
    this.#template = template;
    this.#parentElement = parentElement;
    this.#options = options;

    this.#container = this.#create();
    this.#parentElement.appendChild(this.#container);

    this.#programSelect = this.#container.querySelector(`#programSelect`);
    this.#observationSelect = this.#container.querySelector(`#observationSelect`);

    // Bind the renders and callbacks.
    this.render = this.render.bind(this);
    this.bindCallback = this.bindCallback.bind(this);
  }

  /**
   * Creates the initial DOM by delegating to the template.
   * @return {!HTMLElement}
   * @private
   */
  #create() {
    return this.#template.create();
  }

  /**
   * Re-populate the program <select> after new data arrive.
   * @param {!Array<!Object>} programs
   * @private
   */
  #updatePrograms(programs) {
    // Reset except for the default.
    this.#programSelect.length = 1;

    const frag = document.createDocumentFragment();
    programs.forEach((p) => {
      frag.appendChild(this.#template.createSelectOption(p));
    });

    this.#programSelect.appendChild(frag);
  }

  /**
   * Re-populate the observation <select> after new data arrive.
   * @param {!Array<!Object>} observations
   * @private
   */
  #updateObservations(observations) {
    // Reset except for the default.
    this.#observationSelect.length = 1;

    const frag = document.createDocumentFragment();
    observations.forEach((o) => {
      frag.appendChild(this.#template.createSelectOption(o));
    });

    this.#observationSelect.appendChild(frag);

    this.#observationSelect.disabled = false;
  }

  /**
   * Update other DOM bits that depend on the selected observation.
   * (Placeholder for future work.)
   * @param {!Object} observation
   * @private
   */
  #updateObservation(observation) {
    console.log("Called updating the observation information.");
  }

  /**
   * Render hook called by the controller.
   *
   * @param {String} viewCmd  Command string.
   * @param {{programs: !Array<!Object>}} parameter  Payload.
   */
  render(viewCmd, parameter) {
    switch (viewCmd) {
      case "updatePrograms":
        this.#updatePrograms(parameter.programs);
        break;
      case "updateObservations":
        this.#updateObservations(parameter.observations);
        break;
      case "updateObservation":
        this.#updateObservation(parameter.observation);
        break;
      case "resetObservationSelect":
        this.#observationSelect.length = 1;
        this.#observationSelect.disabled = parameter.disabled;
        break;
    }
  }

  /**
   * Register controller callbacks for DOM events.
   *
   * @param {String} event
   * @param {function()} handler
   */
  bindCallback(event, handler) {
    switch (event) {
      case "selectProgram":
        Utils.on(this.#programSelect, "change", (e) => {
          console.log("triggered program change.", e.target.value);
          handler({ programId: e.target.value });
        });
        break;
      case "selectObservation":
        Utils.on(this.#observationSelect, "change", (e) => {
          console.log("triggered observation change.", e.target.value);
          handler({ observationId: e.target.value });
        });
        break;
    }
  }
}

/**
 * Controller layer: mediates between model and view.
 *
 * @class
 */
class GPPController {
  #options;
  #model;
  #view;

  /**
   * Hook up model ↔ view wiring and register event callbacks.
   * @param {GPPModel} model
   * @param {GPPView}  view
   * @param {Object}   options
   */
  constructor(model, view, options) {
    this.#model = model;
    this.#view = view;
    this.#options = options;

    // Bind the callbacks.
    this.#view.bindCallback("selectProgram", (item) =>
      this.#selectProgram(item.programId)
    );
    this.#view.bindCallback("selectObservation", (item) =>
      this.#selectObservation(item.observationId)
    );
  }

  /**
   * First-time initialisation: fetch programs then ask view to render.
   *
   * @async
   * @return {Promise<void>}
   */
  async init() {
    await this.#model.fetchPrograms();
    this.#view.render("updatePrograms", { programs: this.#model.programsList });
  }

  /**
   * Fired when the user picks a program.
   * @private
   */
  async #selectProgram(programId) {
    this.#view.render("resetObservationSelect", { disabled: true });
    await this.#model.fetchObservations(programId);
    this.#view.render("updateObservations", {
      observations: this.#model.observationsList,
    });
  }

  /**
   * Fired when the user picks an observation.
   * @private
   */
  #selectObservation(observationId) {
    console.log("Controller selected observation.");
    const observation = this.#model.getObservation(observationId);
    this.#view.render("updateObservation", { observation });
  }
}

/**
 * Application for interacting with the GPP.
 *
 * Usage:
 * ```js
 * const widget = new GPP(document.getElementById('placeholder'));
 * await widget.init();
 * ```
 *
 * @class
 */
class GPP {
  static #defaultOptions = {};

  #options;
  #model;
  #template;
  #view;
  #controller;

  /**
   * Bootstraps a complete GPP widget inside the given element.
   * @param {HTMLElement} parentElement  Where the widget should be rendered.
   * @param {Object=}     options        Optional config overrides.
   */
  constructor(parentElement, options = {}) {
    this.#options = { ...GPP.#defaultOptions, ...options, api: window.api };
    this.#model = new GPPModel(this.#options);
    this.#template = new GPPTemplate(this.#options);
    this.#view = new GPPView(this.#template, parentElement, this.#options);
    this.#controller = new GPPController(this.#model, this.#view, this.#options);
  }

  /**
   * Initialise the widget (fetch data & render UI).
   *
   * @async
   * @return {Promise<void>}
   */
  async init() {
    await this.#controller.init();
  }
}

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

    const col1 = Utils.createElement("div", ["col-12"]);
    col1.append(this.#createSelect("program", "Select A Program"));

    const col2 = Utils.createElement("div", ["col-12"]);
    col2.append(this.#createSelect("observation", "TODO"));

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
    option.textContent = `${data.id} | ${data.name}`;

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
   * @param {string} optionHint  Placeholder text.
   * @returns {!HTMLSelectElement}
   * @private
   */
  #createSelect(id, optionHint) {
    const select = Utils.createElement("select", ["form-select"]);
    select.id = `${id}Select`;
    select.innerHTML = `<option value="" selected hidden>${optionHint}</option>`;

    return select;
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
    try {
      const response = await this.#api.get(this.#programsUrl);

      // Fill / refresh the Map.
      this.clearPrograms();
      const programs = response.matches;

      for (const program of programs) {
        this.#programs.set(program.id, program);
      }
    } catch (error) {
      console.error("Error fetching programs:", error);
    }
  }

  // async fetchObservations() {
  //   try {
  //     const response = await this.#api.get(this.#observationsUrl);

  //     // Fill / refresh the Map.
  //     this.clearObservations();
  //     const observations = response.matches;

  //     for (const observation of observations) {
  //       this.#observations.set(observation.id, observation);
  //     }
  //   } catch (error) {
  //     console.error("Error fetching observations:", error);
  //   }
  // }

  // getObservation(observationId) {
  //   return this.#observations.get(observationId);
  // }

  // get observationsList() {
  //   return Array.from(this.#observations.values());
  // }

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

  // get observationsIds() {
  //   return Array.from(this.#observations.keys());
  // }
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
   * Replace all `<option>`s in the program `<select>` except the
   * first “placeholder” one.
   *
   * @param {!Array<!Object>} programs  List of programs.
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
          handler();
        });
        break;
      case "selectObservation":
        Utils.on(this.#observationSelect, "change", (e) => {
          handler();
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

  constructor(model, view, options) {
    this.#model = model;
    this.#view = view;
    this.#options = options;

    // Bind the callbacks.
    this.#view.bindCallback("selectProgram", () => this.#selectProgram());
    this.#view.bindCallback("selectObservation", () => this.#selectObservation());
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
  #selectProgram() {
    console.log("Controller selected run.");
  }

  /**
   * Fired when the user picks an observation.
   * @private
   */
  #selectObservation() {
    console.log("Controller selected observation.");
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

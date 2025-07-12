/**
 * GMOS-N Long-slit field map
 * --------------------------
 * section   : string        - render header
 * id        : string        – required DOM id for the control
 * path      : string        - dotted route to the value in the JSON
 * labelText : string        - label text (default = last segment of path)
 * element   : "input"|"textarea" (default "input")
 * type      : any <input type=""> (default "text")
 * prefix    : string        - input-group addon on the left
 * suffix    : string        - input-group addon on the right
 * colSize   : "col-"        - bootstrap col classes (default "col-sm-6")
 * dynamic   : "brightness"  - treat path as array; build one field / entry
 *
 * Notes
 * -----
 * - If `path` resolves undefined or null it is skipped automatically.
 */
const GMOS_N_LONGSLIT_FIELDS = [
  // Details section.
  { section: "Details" },
  { labelText: "Instrument", path: "instrument", id: "instrument" },
  { labelText: "ID", path: "id", id: "id" },
  { labelText: "Title", path: "title", id: "title" },
  {
    labelText: "Radial Velocity",
    path: "target_environment.first_science_target.sidereal.radial_velocity.kilometers_per_second",
    suffix: "km/s",
    type: "number",
    id: "radialVelocity",
  },
  {
    labelText: "Position Angle",
    path: "pos_angle_constraint.angle.degrees",
    suffix: "deg",
    type: "number",
    id: "posAngle",
  },
  { labelText: "Science Band", path: "science_band" },
  {
    labelText: "Observer Notes",
    path: "observer_notes",
    element: "textarea",
    colSize: "col-12",
    id: "observerNotes",
  },
  // Brightnesses section.
  { section: "Brightnesses" },
  {
    path: "target_environment.first_science_target.source_profile.point.band_normalized.brightnesses",
    dynamic: "brightnesses",
    id: "brightness",
    colSize: "col-md-6",
  },
  // Constraint section.
  { section: "Constraint Set" },
  {
    labelText: "Image Quality",
    path: "constraint_set.image_quality",
    id: "imageQuality",
  },
  {
    labelText: "Cloud Extinction",
    path: "constraint_set.cloud_extinction",
    id: "cloudExtinction",
  },
  {
    labelText: "Sky Background",
    path: "constraint_set.sky_background",
    id: "skyBackground",
  },
  { labelText: "Water Vapor", path: "constraint_set.water_vapor", id: "waterVapor" },
];

const getByPath = (obj, p) =>
  p
    .replace(/\[(\d+)]/g, ".$1")
    .split(".")
    .reduce((o, k) => (o && o[k] !== undefined ? o[k] : undefined), obj);

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
    const row = Utils.createElement("div", ["row", "g-3", "mb-3"]);

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
    container.append(row, Utils.createElement("hr"));

    return container;
  }

  createObservationForm(observation) {
    let form;
    if (
      ["GMOS_NORTH_LONG_SLIT", "GMOS_SOUTH_LONG_SLIT"].includes(
        observation.observing_mode.mode
      )
    ) {
      form = this._createGMOSLongslitForm(observation);
    }
    return form;
  }

  _createGMOSLongslitForm(observation) {
    const form = Utils.createElement("form", ["row", "g-3"]);

    GMOS_N_LONGSLIT_FIELDS.forEach((meta) => {
      // Create section header.
      if (meta.section) {
        form.append(this._createFormHeader(meta.section));
        return;
      }

      // Get value.
      const raw = getByPath(observation, meta.path);
      if (raw == null) {
        console.log("Could not find:", meta.path);
        return;
      }

      // Handle brightness array.
      if (meta.dynamic === "brightnesses") {
        raw.forEach(({ band, value, units }, idx) => {
          form.append(
            this._createFormField({
              value,
              id: `${meta.id}${idx}`,
              prefix: band,
              suffix: units,
              type: "number",
              colSize: meta.colSize,
            })
          );
        });
        return;
      }

      // Handle normal field
      form.append(
        this._createFormField({
          value: raw,
          id: meta.id,
          labelText: meta.labelText,
          prefix: meta.prefix,
          suffix: meta.suffix,
          element: meta.element,
          type: meta.type,
          colSize: meta.colSize,
        })
      );
    });

    return form;
  }

  _createFormHeader(text, level = "h5") {
    const h = Utils.createElement(level, ["mt-4", "mb-0"]);
    h.textContent = text;
    return h;
  }

  _wrapWithGroup(control, { prefix, suffix }) {
    if (!prefix && !suffix) return control;

    const group = Utils.createElement("div", ["input-group"]);
    if (prefix) {
      const pre = Utils.createElement("span", ["input-group-text"]);
      pre.textContent = prefix;
      group.append(pre);
    }
    group.append(control);
    if (suffix) {
      const post = Utils.createElement("span", ["input-group-text"]);
      post.textContent = suffix;
      group.append(post);
    }
    return group;
  }

  _createFormField({
    value,
    id,
    labelText = null,
    prefix = null,
    suffix = null,
    element = "input",
    type = "text",
    colSize = "col-sm-6",
  }) {
    // Skip silently if value is undefined/null.
    if (value == null || !id) {
      console.log("Nothing to display:", value, id);
      return Utils.createElement("div");
    }
    const elementId = `${id}${Utils.capitalizeFirstLetter(element)}`;
    const col = Utils.createElement("div", [colSize]);
    // Create label.
    if (labelText) {
      const label = Utils.createElement("label", ["form-label"]);
      label.htmlFor = elementId;
      label.textContent = labelText;
      col.append(label);
    }

    // Create input.
    let control;
    if (element === "textarea") {
      control = Utils.createElement("textarea", ["form-control"]);
      control.rows = 3;
    } else if (element === "input") {
      control = Utils.createElement("input", ["form-control"]);
      control.type = type;
    } else {
      console.error("Unsupported element:", element);
      return col;
    }
    control.id = elementId;
    control.value = value;
    control.disabled = true;

    // Wrap in input group if needed.
    col.append(this._wrapWithGroup(control, { prefix, suffix }));
    return col;
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
      // FIXME: Remove .observations after fix in gpp-client
      const observations = response.observations.matches;

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
    const form = this.#template.createObservationForm(observation);
    this.#container.append(form);
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

  async test() {
    await this.#model.fetchObservations("p-143");
    this.#view.render("updateObservation", {
      observation: this.#model.getObservation("o-146"),
    });
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

  async test() {
    await this.#controller.test();
  }
}

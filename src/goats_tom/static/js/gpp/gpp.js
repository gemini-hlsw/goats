const ENABLE_CREATE_NEW_OBSERVATION = false;
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

    const col1 = Utils.createElement("div", ["col-12"]);
    const p = Utils.createElement("p", ["mb-0", "fst-italic"]);
    p.textContent =
      "Use the Gemini Program Platform (GPP) to browse your active programs and corresponding observations. Select a program to load its observations and autofill observation details. You can then save the observation on GOATS without changes,  update the observation details and resubmit, or create a new observation for a ToO. Any updates or new observations are saved on GOATS automatically upon submission.";
    col1.append(p);

    const div = Utils.createElement("div");
    div.id = "programObservationsPanelContainer";
    row.append(col1, div);

    // Create form container.
    const formContainer = Utils.createElement("div");
    formContainer.id = "formContainer";
    container.append(row, Utils.createElement("hr"), formContainer);

    return container;
  }

  createCreateNewObservation() {
    const form = Utils.createElement("form");
    // Set the fields to build in details sections.
    const firstFields = [
      { section: "Details" },
      {
        labelText: "State",
        element: "select",
        options: ["Ready", "Defined", "Inative"],
        id: "state",
      },
      {
        labelText: "Radial Velocity",
        suffix: "km/s",
        type: "number",
        id: "radialVelocity",
      },
      {
        labelText: "Parallax",
        suffix: "mas",
        type: "number",
        id: "parallax",
      },
      {
        labelText: "\u03BC RA",
        suffix: "mas/year",
        type: "number",
        id: "uRa",
      },
      {
        labelText: "\u03BC Dec",
        suffix: "mas/year",
        type: "number",
        id: "uDec",
      },
      {
        labelText: "Observer Notes",
        element: "textarea",
        colSize: "col-12",
        id: "observerNotes",
      },
    ];
    const secondFields = [
      { section: "Constraints" },
      {
        labelText: "Image Quality",
        element: "select",
        id: "imageQuality",
        options: [
          "< 0.10 arcsec",
          "< 0.20 arcsec",
          "< 0.30 arcsec",
          "< 0.40 arcsec",
          "< 0.60 arcsec",
          "< 0.80 arcsec",
          "< 1.00 arcsec",
          "< 1.50 arcsec",
          "< 2.00 arcsec",
        ],
      },
      {
        labelText: "Cloud Extinction",
        element: "select",
        id: "cloudExtinction",
        options: [
          "0.00 mag",
          "< 0.10 mag",
          "< 0.30 mag",
          "< 0.50 mag",
          "< 1.00 mag",
          "< 2.00 mag",
          "< 3.00 mag",
        ],
      },
      {
        labelText: "Water Vapor",
        element: "select",
        id: "waterVapor",
        options: ["Very Dry", "Dry", "Median", "Wet"],
      },
      {
        labelText: "Sky Background",
        element: "select",
        id: "skyBackground",
        options: ["Darkest", "Dark", "Gray", "Bright"],
      },
      {
        labelText: "Elevation Range",
        element: "select",
        id: "elevationRange",
        options: ["Hour Angle", "Air Mass"],
      },
      {
        labelText: "Hour Angle Minimum",
        element: "input",
        id: "haMinimum",
        suffix: "hours",
        value: -5.0,
        type: "number",
      },
      {
        labelText: "Hour Angle Maximum",
        element: "input",
        id: "haMaximum",
        suffix: "hours",
        value: 5.0,
        type: "number",
      },
      {
        labelText: "Air Mass Minimum",
        element: "input",
        id: "airMassMinimum",
        visible: false,
        value: 1.0,
        type: "number",
      },
      {
        labelText: "Air Mass Maximum",
        element: "input",
        id: "airMassMaximum",
        visible: false,
        value: 2.0,
        type: "number",
      },
      { section: "Configuration" },
      {
        labelText: "",
        element: "select",
        id: "instrumentConfiguration",
        options: ["Loading..."],
        disabled: true,
        colSize: "col-12",
      },
    ];
    // Build the fields and attach to the row in a details section.
    const firstRow = Utils.createElement("div", ["row", "g-3", "mb-3"]);
    this.#appendFieldsToRow(firstRow, firstFields);
    form.append(firstRow);

    // Build the source profile.
    const sourceProfileDiv = Utils.createElement("div");
    new SourceProfileEditor(sourceProfileDiv);
    form.append(sourceProfileDiv);

    // Build the brightnesses section.
    form.append(this.#createFormHeader("Brightnesses"));
    const div = Utils.createElement("div", "mt-3");
    new BrightnessesEditor(div);
    form.append(div);

    const secondRow = Utils.createElement("div", ["row", "g-3", "mb-3"]);
    this.#appendFieldsToRow(secondRow, secondFields);
    form.append(secondRow);

    // Attach the event listener for elevation range changes. Didn't deem it big enough
    // to require its own application like source profile or brightnesses.
    this.#attachElevationRangeListener(form);

    const btn = Utils.createElement("button", ["btn", "btn-primary", "mt-4"]);
    btn.textContent = "Create And Save";
    btn.id = "createAndSaveObservationButton";
    btn.type = "button";
    btn.dataset.action = "createAndSaveObservation";

    form.append(btn);

    return form;
  }

  /**
   * Append form fields to a Bootstrap row element using metadata definitions.
   * This method supports both regular form fields and section headers.
   *
   * @param {!HTMLElement} row - The Bootstrap row element to which fields will be appended.
   * @param {!Array<Object>} fields - List of field metadata objects.
   * @private
   */
  #appendFieldsToRow(row, fields) {
    fields.forEach((meta) => {
      if (meta.section) {
        row.append(this.#createFormHeader(meta.section));
      } else {
        row.append(
          this.#createFormField({
            value: meta.value,
            id: meta.id,
            labelText: meta.labelText,
            prefix: meta.prefix,
            suffix: meta.suffix,
            element: meta.element,
            type: meta.type,
            colSize: meta.colSize,
            disabled: meta.disabled,
            options: meta.options,
            visible: meta.visible,
          })
        );
      }
    });
  }

  /**
   * Attach event listener to the elevation range select field to toggle visibility.
   * @param {HTMLFormElement} form - The form containing elevation fields.
   * @private
   */
  #attachElevationRangeListener(form) {
    // TODO: This could be moved to delegation if deemed so.
    const select = form.querySelector("#elevationRangeSelect");
    const haMinCol = form.querySelector("#haMinimumInput")?.closest(".col-md-6");
    const haMaxCol = form.querySelector("#haMaximumInput")?.closest(".col-md-6");
    const amMinCol = form.querySelector("#airMassMinimumInput")?.closest(".col-md-6");
    const amMaxCol = form.querySelector("#airMassMaximumInput")?.closest(".col-md-6");

    if (!select || !haMinCol || !haMaxCol || !amMinCol || !amMaxCol) return;

    Utils.on(select, "change", (e) => {
      const isHA = e.target.value === "Hour Angle";
      haMinCol.classList.toggle("d-none", !isHA);
      haMaxCol.classList.toggle("d-none", !isHA);
      amMinCol.classList.toggle("d-none", isHA);
      amMaxCol.classList.toggle("d-none", isHA);
    });
  }

  /**
   * Create a form for a selected observation using shared and mode-specific fields.
   * @param {!Object} observation - Observation data to render.
   * @returns {!HTMLFormElement} A completed form element.
   */
  createSaveObservationForm(observation) {
    const form = Utils.createElement("form", ["row", "g-3"]);
    const sharedFields = [...SHARED_FIELDS];
    const mode = observation.observingMode?.mode;
    const instrumentFields = FIELD_CONFIGS[mode];

    if (!instrumentFields) {
      console.warn(
        `Unsupported observing mode: "${mode}". No instrument-specific fields will be rendered.`
      );
    }

    const allFields = [...sharedFields, ...(instrumentFields ?? [])];

    allFields.forEach((meta) => {
      // Create section header.
      if (meta.section) {
        form.append(this.#createFormHeader(meta.section));
        return;
      }
      // Get value.
      const raw = Utils.getByPath(observation, meta.path);
      const shouldShow = meta.display || raw != null;
      if (!shouldShow) return;

      // Format raw if formatter or lookup is provided.
      const lookedUp = meta.lookup ? meta.lookup[raw] ?? raw : raw;
      const formatted = meta.formatter ? meta.formatter(lookedUp) : lookedUp;

      // Check if custom handler is attached.
      if (meta.handler) {
        const handler = this.#handlers[meta.handler];
        if (typeof handler === "function") {
          const elements = handler(meta, formatted);
          elements.forEach((el) => form.append(el));
        } else {
          console.warn(
            `Handler "${meta.handler}" not found for field "${meta.id}". Skipping.`
          );
        }
        return;
      }

      // Handle normal field
      form.append(
        this.#createFormField({
          value:
            meta.type === "number" && formatted == null
              ? ""
              : formatted ?? "(No value)",
          id: meta.id,
          labelText: meta.labelText,
          prefix: meta.prefix,
          suffix: meta.suffix,
          element: meta.element,
          type: meta.type,
          colSize: meta.colSize,
          disabled: true,
          options: meta.options,
          visible: meta.visible,
        })
      );
    });

    return form;
  }

  /**
   * Create a section header element for form sections.
   * @param {string} text - Header text content.
   * @param {string} [level="h5"] - Heading level tag.
   * @returns {!HTMLElement}
   * @private
   */
  #createFormHeader(text, level = "h5") {
    const h = Utils.createElement(level, ["mt-4", "mb-0"]);
    h.textContent = text;
    return h;
  }

  /**
   * Wraps a form control with prefix/suffix in an input group if applicable.
   * @param {!HTMLElement} control - The form element to wrap.
   * @param {Object} options
   * @param {string=} options.prefix - Optional prefix text.
   * @param {string=} options.suffix - Optional suffix text.
   * @returns {!HTMLElement}
   * @private
   */
  #wrapWithGroup(control, { prefix, suffix }) {
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

  /**
   * Create a form field from metadata.
   * @param {Object} field - Field configuration metadata.
   * @param {string} field.id - Field ID.
   * @param {*} field.value - Initial field value.
   * @param {string=} field.labelText - Field label.
   * @param {string=} field.prefix - Optional prefix text.
   * @param {string=} field.suffix - Optional suffix text.
   * @param {string=} field.element - Element type: input, textarea, or select.
   * @param {string=} field.type - Input type (e.g., "number", "text").
   * @param {string=} field.colSize - Bootstrap column class.
   * @param {boolean=} field.disabled - Whether the field is disabled.
   * @param {boolean=} field.visible - Whether the field is visible or not.
   * @param {Array<string|{labelText: string, value: string}>=} field.options - Options for a
   * select element.
   * @returns {!HTMLElement}
   * @private
   */
  #createFormField({
    id,
    value = "",
    labelText = null,
    prefix = null,
    suffix = null,
    element = "input",
    type = "text",
    colSize = "col-md-6",
    disabled = false,
    visible = true,
    options = [],
  }) {
    const elementId = `${id}${Utils.capitalizeFirstLetter(element)}`;
    const col = Utils.createElement("div", [colSize]);

    // Create label.
    if (labelText) {
      const label = Utils.createElement("label", ["form-label"]);
      label.htmlFor = elementId;
      label.textContent = labelText;
      col.append(label);
    }

    // Create form control.
    let control;
    if (element === "textarea") {
      control = Utils.createElement("textarea", ["form-control"]);
      control.rows = 3;
      control.value = value;
    } else if (element === "input") {
      control = Utils.createElement("input", ["form-control"]);
      control.type = type;
      control.value = value;
    } else if (element === "select") {
      control = Utils.createElement("select", ["form-select"]);
      options.forEach((opt) => {
        const optionEl = Utils.createElement("option");
        // Handle if option passed in is just a list of strings.
        if (typeof opt === "string") {
          optionEl.value = opt;
          optionEl.textContent = opt;
        } else {
          // User passed in JSON object {value: "", labelText: ""}
          optionEl.value = opt.value;
          optionEl.textContent = opt.label;
        }
        if (optionEl.value === value) {
          optionEl.selected = true;
        }
        control.appendChild(optionEl);
      });
    } else {
      console.error("Unsupported element:", element);
      return col;
    }

    control.id = elementId;
    control.disabled = disabled;

    if (!visible) {
      col.classList.add("d-none");
    }

    // Wrap and append.
    col.append(this.#wrapWithGroup(control, { prefix, suffix }));
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

    // Add inline spinner next to label.
    const spinner = Utils.createElement("span", [
      "spinner-border",
      "spinner-border-sm",
      "ms-2",
    ]);
    spinner.id = `${id}Loading`;
    spinner.role = "status";
    spinner.hidden = true;
    label.appendChild(spinner);

    const select = Utils.createElement("select", ["form-select"]);
    select.id = `${id}Select`;
    select.innerHTML = `<option value="" selected hidden>${optionHint}</option>`;
    select.disabled = true;

    const wrapper = Utils.createElement("div");
    wrapper.append(label, select);

    return wrapper;
  }

  /**
   * Custom handlers for rendering advanced field types.
   * @returns {Object<string, function(Object, *): HTMLElement[]>}
   * @private
   */
  get #handlers() {
    return {
      handleBrightnessInputs: (meta, raw) => {
        return raw.map(({ band, value, units }, idx) =>
          this.#createFormField({
            value,
            id: `${meta.id}${idx}`,
            prefix: band,
            suffix: units,
            type: meta.type,
            colSize: meta.colSize,
            disabled: true,
            visible: meta.visible,
          })
        );
      },
      handleSpatialOffsetsList: (meta, raw) => {
        const values = raw.map((o) => o.arcseconds.toFixed(2));
        return [
          this.#createFormField({
            value: values.join(", "),
            id: meta.id,
            labelText: meta.labelText,
            suffix: meta.suffix,
            colSize: meta.colSize,
            disabled: true,
            visible: meta.visible,
          }),
        ];
      },
      handleWavelengthDithersList: (meta, raw) => {
        const values = raw.map((o) => o.nanometers.toFixed(1));
        return [
          this.#createFormField({
            value: values.join(", "),
            id: meta.id,
            labelText: meta.labelText,
            suffix: meta.suffix,
            colSize: meta.colSize,
            disabled: true,
            visible: meta.visible,
          }),
        ];
      },
      handleExposureMode: (meta, raw) => {
        const modeKey = Object.keys(raw).find((key) => raw[key] != null);
        const modeLabels = {
          signalToNoise: "Signal / Noise",
          timeAndCount: "Time & Count",
        };
        const label = modeLabels[modeKey] ?? "(Unknown)";
        return [
          this.#createFormField({
            value: label,
            id: meta.id,
            labelText: meta.labelText,
            disabled: true,
            visible: meta.visible,
          }),
        ];
      },
    };
  }
}

/**
 * Handles remote I/O and caches the results.
 * @class
 */
class GPPModel {
  #options;
  #api;
  #userId;
  #targetId;
  #facility;
  // Url specific variables.
  #gppUrl = "gpp/";
  #gppProgramsUrl = `${this.#gppUrl}programs/`;
  #gppObservationsUrl = `${this.#gppUrl}observations/`;
  #gppPingUrl = `${this.#gppUrl}ping/`;
  #observationsUrl = `observations/`;

  // Data-storing maps.
  #normalObservations = new Map();
  #tooObservations = new Map();
  #programs = new Map();
  #activeObservation;

  constructor(options) {
    this.#options = options;
    this.#api = this.#options.api;
    this.#userId = this.#options.userId;
    this.#facility = this.#options.facility;
    this.#targetId = this.#options.targetId;
  }

  /** Clears every cached observation and active observation. */
  clearObservations() {
    this.#normalObservations.clear();
    this.#tooObservations.clear();
    this.#activeObservation = null;
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
   * Checks if the GPP backend is reachable by issuing a GET request to the ping endpoint.
   * @returns {Object} An object containing the HTTP status code and a human-readable detail
   * message.
   */
  async isReachable() {
    try {
      const response = await this.#api.get(this.#gppPingUrl);
      return { status: 200, detail: response.detail };
    } catch (error) {
      // Have to unpack the error still.
      const data = await error.json();
      return data;
    }
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
      const response = await this.#api.get(this.#gppProgramsUrl);

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
   * Submits an observation to the backend API.
   * @param {Object} observation The observation object to save.
   * @returns {Promise<{status: number, data: Object}>} A response object with status code and response data.
   */
  // FIXME: Update the right way
  async saveObservation(observation) {
    // User isn't needed.
    const data = {
      target_id: this.#targetId,
      facility: this.#facility,
      // Need to pass in the instrument to select the correct form.
      observation_type: observation.instrument,
      observing_parameters: observation,
    };
    try {
      const response = await this.#api.post(this.#observationsUrl, data);
      return { status: 200, data: response };
    } catch (error) {
      const data = await error.json();
      return { status: data.status, data: data };
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
      const { matches, hasMore } = await this.#api.get(
        `${this.#gppObservationsUrl}?program_id=${programId}`
      );

      const tooResults = matches?.too?.results ?? [];
      const normalResults = matches?.normal?.results ?? [];

      // Helper to bulk-fill a map from results.
      const fillMap = (map, results) => {
        for (const obs of results) {
          map.set(obs.id, obs);
        }
      };

      fillMap(this.#tooObservations, tooResults);
      fillMap(this.#normalObservations, normalResults);
    } catch (error) {
      console.error("Error fetching observations:", error);
    }
  }

  get tooObservationsCount() {
    return this.#tooObservations.size;
  }

  get normalObservationsCount() {
    return this.#normalObservations.size;
  }

  /**
   * Get a too observation object that is already in the cache. Also sets the active
   * observation to track the last retrieved.
   * @param {string} observationId
   * @returns {Object|undefined}
   */
  getTooObservation(observationId) {
    const obs = this.#tooObservations.get(observationId);
    this.#activeObservation = obs || null;
    return obs;
  }

  /**
   * Get a normal observation object that is already in the cache. Also sets the active
   * observation to track the last retrieved.
   * @param {string} observationId
   * @returns {Object|undefined}
   */
  getNormalObservation(observationId) {
    const obs = this.#normalObservations.get(observationId);
    this.#activeObservation = obs || null;
    return obs;
  }

  /**
   * The last retrieved observation from cache.
   * @returns {Object|null}
   */
  get activeObservation() {
    return this.#activeObservation;
  }

  /**
   * All cached too observations as an array.
   * @type {!Array<!Object>}
   */
  get tooObservationsList() {
    return Array.from(this.#tooObservations.values());
  }

  /**
   * All cached too observation IDs.
   * @type {!Array<string>}
   */
  get tooObservationsIds() {
    return Array.from(this.#tooObservations.keys());
  }

  /**
   * All cached normal observations as an array.
   * @type {!Array<!Object>}
   */
  get normalObservationsList() {
    return Array.from(this.#normalObservations.values());
  }

  /**
   * All cached normal observation IDs.
   * @type {!Array<string>}
   */
  get normalObservationsIds() {
    return Array.from(this.#normalObservations.keys());
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
  #form;
  #formContainer;
  #poPanel; // ProgramObservationsPanel instance.

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
    this.#formContainer = this.#container.querySelector(`#formContainer`);
    this.#parentElement.appendChild(this.#container);

    this.#poPanel = new ProgramObservationsPanel(
      this.#container.querySelector(`#programObservationsPanelContainer`),
      { debug: false }
    );

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
   * Update other DOM bits that depend on the selected observation.
   * @param {!Object} observation
   * @private
   */
  #updateObservation(observation) {
    const form = this.#template.createSaveObservationForm(observation);
    this.#form = form;
    this.#formContainer.append(this.#form);
  }

  /**
   * Clear the current observation form.
   * @private
   */
  #clearObservationForm() {
    this.#formContainer.innerHTML = "";
    this.#form = null;
  }

  #showCreateNewObservation() {
    const form = this.#template.createCreateNewObservation();
    this.#form = form;
    this.#formContainer.append(this.#form);
  }

  /**
   * Render hook called by the controller.
   * @param {String} viewCmd  Command string.
   * @param {Object} parameter  Payload of parameters.
   */
  render(viewCmd, parameter) {
    switch (viewCmd) {
      // Program renders.
      case "updatePrograms":
        this.#poPanel.updatePrograms(parameter.programs);
        break;
      case "programsLoading":
        this.#poPanel.toggleProgramsLoading(true);
        break;
      case "programsLoaded":
        this.#poPanel.toggleProgramsLoading(false);
        break;

      // Normal observation renders.
      case "updateNormalObservations":
        this.#poPanel.updateNormalObservations(parameter.observations);
        break;
      case "resetNormalObservations":
        this.#poPanel.clearNormalSelect();
        this.#clearObservationForm();
        break;
      case "normalObservationsLoading":
        this.#poPanel.toggleNormalLoading(true);
        break;
      case "normalObservationsLoaded":
        this.#poPanel.toggleNormalLoading(false);
        break;

      // ToO observation renders.
      case "updateTooObservations":
        this.#poPanel.updateTooObservations(parameter.observations);
        break;
      case "showCreateNewObservation":
        this.#showCreateNewObservation();
        break;
      case "resetTooObservations":
        this.#poPanel.clearTooSelect();
        this.#clearObservationForm();
        break;
      case "tooObservationsLoading":
        this.#poPanel.toggleTooLoading(true);
        break;
      case "tooObservationsLoaded":
        this.#poPanel.toggleTooLoading(false);
        break;

      // Form renders.
      case "clearObservationForm":
        this.#clearObservationForm();
        break;

      // Misc. renders.
      case "updateObservation":
        this.#updateObservation(parameter.observation);
        break;
    }
  }

  /**
   * Register controller callbacks for DOM events.
   * @param {String} event
   * @param {function()} handler
   */
  bindCallback(event, handler) {
    const selector = `[data-action="${event}"]`;
    switch (event) {
      case "selectProgram":
        console.log("binded program select");
        this.#poPanel.onProgramSelect((id) => handler({ programId: id }));
        break;
      case "selectNormalObservation":
        console.log("binded normal select");
        this.#poPanel.onNormalSelect((id) => handler({ observationId: id }));
        break;
      case "selectTooObservation":
        console.log("binded too select");
        this.#poPanel.onTooSelect((id) => handler({ observationId: id }));
        break;
      case "editObservation":
        console.log("binded edit observation");
        this.#poPanel.onEdit(handler);
        break;
      case "saveObservation":
        console.log("binded save observation");
        this.#poPanel.onSave(handler);
        break;
      case "createNewObservation":
        console.log("binded create new observation");
        this.#poPanel.onCreateNew(handler);
        break;
      case "createAndSaveObservation":
        Utils.delegate(this.#formContainer, selector, "click", (e) => {
          e.preventDefault();
          handler();
        });
        break;
    }
  }
}

/**
 * Controller layer: mediates between model and view.
 * @class
 */
class GPPController {
  #options;
  #model;
  #view;
  #toast;

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
    this.#toast = options.toast;

    // Bind the callbacks.
    this.#view.bindCallback("selectNormalObservation", (item) =>
      console.log("Controller got the normal observation.")
    );
    this.#view.bindCallback("selectTooObservation", (item) =>
      console.log("Controller got the too observation.")
    );
    this.#view.bindCallback("editObservation", () =>
      console.log("Controller got the edit observation.")
    );
    this.#view.bindCallback("selectProgram", (item) =>
      this.#selectProgram(item.programId)
    );
    this.#view.bindCallback("selectObservation", (item) =>
      this.#selectObservation(item.observationId)
    );
    this.#view.bindCallback("saveObservation", () => this.#saveObservation());
    this.#view.bindCallback("createNewObservation", (item) =>
      this.#createNewObservation()
    );
    this.#view.bindCallback("createAndSaveObservation", () =>
      this.#createAndSaveObservation()
    );
  }

  #createNewObservation() {
    this.#view.render("clearObservationForm");
    this.#view.render("showCreateNewObservation");
  }

  #createAndSaveObservation() {
    console.log("Controller got the create and save");
  }

  /**
   * Handles the process of saving an observation and displaying a toast notification
   * based on the result. Shows a warning if the observation has no reference,
   * a success toast if saved successfully, or an error toast with details if it fails.
   * @private
   * @returns {Promise<void>}
   */
  async #saveObservation() {
    const observation = this.#model.activeObservation;

    // Skip if no observation reference has been set aka null or undefined.
    let notification = {};
    if (observation?.reference?.label == null) {
      notification = {
        label: "Observation Not Saved",
        message:
          "Observation not saved, as no observation reference ID has been assigned.",
        color: "warning",
      };
      this.#toast.show(notification);
      return;
    }

    const response = await this.#model.saveObservation(observation);

    if (response.status === 200) {
      notification = {
        label: "Observation Saved Successfully",
        message: `Observation ID ${observation.reference.label} has been saved to GOATS.`,
        color: "success",
      };
    } else {
      // Gracefully extract and format error messages.
      const errorMessages = Object.values(response.data).flat().join(" ");

      notification = {
        label: "Observation Not Saved",
        message:
          errorMessages || "An unknown error occurred while saving the observation.",
        color: "danger",
      };
    }
    this.#toast.show(notification);
  }

  /**
   * First-time initialization: fetch programs then ask view to render.
   * @async
   * @return {Promise<void>}
   */
  async init() {
    const { status, detail } = await this.#model.isReachable();
    if (status !== 200) {
      // Build toast.
      const notification = {
        label: "GPP Communication Error",
        message: detail ?? "Unknown error, please try again later.",
        color: "danger",
      };
      this.#toast.show(notification);
      // Exit and do nothing else.
      return;
    }
    this.#view.render("programsLoading");
    await this.#model.fetchPrograms();

    // Check if programs are available.
    const programsList = this.#model.programsList;
    this.#view.render("updatePrograms", { programs: programsList });
    this.#view.render("programsLoaded");
  }

  /**
   * Fired when the user picks a program.
   * @private
   * FIXME: Update this.
   */
  async #selectProgram(programId) {
    this.#view.render("toggleButtonToolbar", { disabled: true });

    // Reset and show loading.
    this.#view.render("resetNormalObservations");
    this.#view.render("resetTooObservations");
    this.#view.render("normalObservationsLoading");
    this.#view.render("tooObservationsLoading");

    await this.#model.fetchObservations(programId);

    // Update both lists in one go.
    this.#view.render("updateNormalObservations", {
      observations: this.#model.normalObservationsList,
    });
    this.#view.render("updateTooObservations", {
      observations: this.#model.tooObservationsList,
    });

    this.#view.render("normalObservationsLoaded");
    this.#view.render("tooObservationsLoaded");
  }

  /**
   * Fired when the user picks an observation.
   * @private
   */
  #selectObservation(observationId) {
    this.#view.render("clearObservationForm");
    const observation = this.#model.getObservation(observationId);
    this.#view.render("updateObservation", { observation });
    this.#view.render("toggleButtonToolbar", { disabled: false });
  }
}

/**
 * Application for interacting with the GPP.
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
    const dataset = parentElement.dataset;
    this.#options = {
      ...GPP.#defaultOptions,
      ...options,
      api: window.api,
      toast: window.toast,
      userId: dataset.userId,
      facility: dataset.facility,
      targetId: dataset.targetId,
    };
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

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
      "Use the Gemini Program Platform (GPP) to browse your active programs and corresponding observations. Select a program to load its observations and autofill observation details. You can then either save the observation on GOATS without changes or edit the observation details and submit to Gemini. The latter will save the observation on GOATS automatically upon submission.";
    col1.append(p);

    const col2 = Utils.createElement("div", ["col-lg-6"]);
    col2.append(
      this.#createSelect("program", "Active Programs", "Choose a program...")
    );

    const col3 = Utils.createElement("div", ["col-lg-6"]);
    const observationSelect = this.#createSelect(
      "observation",
      "Active Observations",
      "Choose an observation..."
    );
    col3.append(observationSelect);

    // Create button toolbar.
    const buttonToolbar = Utils.createElement("div", [
      "d-flex",
      "justify-content-between",
    ]);
    buttonToolbar.id = "buttonToolbar";
    const left = Utils.createElement("div");
    const right = Utils.createElement("div");

    const actions = [
      {
        id: "saveButton",
        color: "primary",
        label: "Save",
        parentElement: right,
      },
      {
        id: "editButton",
        color: "secondary",
        label: "Edit",
        parentElement: left,
        classes: ["me-1"],
      },
      {
        id: "editAndCreateNewButton",
        color: "secondary",
        label: "Edit and Create New Observation",
        parentElement: left,
      },
    ];

    actions.forEach(({ id, color, label, parentElement, classes = [] }) => {
      const btn = Utils.createElement("button", ["btn", `btn-${color}`, ...classes]);
      btn.textContent = label;
      btn.id = id;
      btn.type = "button";
      btn.disabled = true;
      parentElement.appendChild(btn);
    });
    buttonToolbar.append(left, right);

    row.append(col1, col2, col3);

    // Create form container.
    const formContainer = Utils.createElement("div");
    formContainer.id = "formContainer";
    container.append(row, buttonToolbar, Utils.createElement("hr"), formContainer);

    return container;
  }

  /**
   * Create a form for a selected observation using shared and mode-specific fields.
   * @param {!Object} observation - Observation data to render.
   * @returns {!HTMLFormElement} A completed form element.
   */
  createObservationForm(observation) {
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
   * @param {Object} options
   * @param {*} options.value - Field value.
   * @param {string} options.id - Field ID.
   * @param {string=} options.labelText - Field label.
   * @param {string=} options.prefix - Optional prefix.
   * @param {string=} options.suffix - Optional suffix.
   * @param {string=} options.element - Element type.
   * @param {string=} options.type - Input type.
   * @param {string=} options.colSize - Bootstrap column size.
   * @returns {!HTMLElement}
   * @private
   */
  #createFormField({
    value,
    id,
    labelText = null,
    prefix = null,
    suffix = null,
    element = "input",
    type = "text",
    colSize = "col-md-6",
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
  #observations = new Map();
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
    this.#observations.clear();
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
      const response = await this.#api.get(
        `${this.#gppObservationsUrl}?program_id=${programId}`
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
   * Get an observation object that is already in the cache. Also sets the active
   * observation to track the last retrieved.
   * @param {string} observationId
   * @returns {Object|undefined}
   */
  getObservation(observationId) {
    const obs = this.#observations.get(observationId);
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
  #form;
  #formContainer;
  #buttonToolbar;
  #editButton;
  #saveButton;
  #editAndCreateNewButton;
  #observationLoading;
  #programLoading;

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

    this.#programSelect = this.#container.querySelector(`#programSelect`);
    this.#programLoading = this.#container.querySelector(`#programLoading`);
    this.#observationSelect = this.#container.querySelector(`#observationSelect`);
    this.#observationLoading = this.#container.querySelector(`#observationLoading`);
    this.#buttonToolbar = this.#container.querySelector(`#buttonToolbar`);
    this.#editButton = this.#buttonToolbar.querySelector("#editButton");
    this.#saveButton = this.#buttonToolbar.querySelector("#saveButton");
    this.#editAndCreateNewButton = this.#buttonToolbar.querySelector(
      "#editAndCreateNewButton"
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
  }

  /**
   * Displays a disabled message in the program <select> indicating that
   * no programs are available for the user. Retains the default placeholder.
   * @private
   */
  #showNoPrograms() {
    this.#programSelect.length = 1;

    const option = Utils.createElement("option");
    option.value = "None";
    option.textContent = "No programs available";
    option.disabled = true;

    this.#programSelect.appendChild(option);
  }

  /**
   * Displays a disabled message in the observation <select> indicating that
   * no observations exist for the selected program. Retains the default placeholder.
   * @private
   */
  #showNoObservations() {
    this.#observationSelect.length = 1;

    const option = Utils.createElement("option");
    option.value = "None";
    option.textContent = "No observations available";
    option.disabled = true;

    this.#observationSelect.appendChild(option);
  }

  /**
   * Update other DOM bits that depend on the selected observation.
   * (Placeholder for future work.)
   * @param {!Object} observation
   * @private
   */
  #updateObservation(observation) {
    const form = this.#template.createObservationForm(observation);
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

  /**
   * Show or hide the loading spinner next to the "Active Programs" label
   * and enable or disable the program <select> element accordingly.
   * @param {boolean} isLoading - Whether to show the spinner and disable the select.
   * @private
   */
  #toggleProgramsLoading(isLoading) {
    this.#programSelect.disabled = isLoading;
    this.#programLoading.hidden = !isLoading;
  }

  /**
   * Show or hide the loading spinner next to the "Active Observations" label
   * and enable or disable the observation <select> element accordingly.
   * @param {boolean} isLoading - Whether to show the spinner and disable the select.
   * @private
   */
  #toggleObservationsLoading(isLoading) {
    this.#observationSelect.disabled = isLoading;
    this.#observationLoading.hidden = !isLoading;
  }

  /**
   * Enables or disables the main toolbar buttons.
   * @param {boolean} disabled - Whether to disable or enable the buttons.
   */
  #toggleButtonToolbar(disabled) {
    this.#saveButton.disabled = disabled;
    // FIXME: Change the edit and edit and create new button later.
    this.#editButton.disabled = true;
    this.#editAndCreateNewButton.disabled = true;
  }

  /**
   * Render hook called by the controller.
   * @param {String} viewCmd  Command string.
   * @param {Object} parameter  Payload of parameters.
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
      case "resetAndClearObservationSelect":
        this.#observationSelect.length = 1;
        this.#clearObservationForm();
        break;
      case "clearObservationForm":
        this.#clearObservationForm();
        break;
      case "programsLoading":
        this.#toggleProgramsLoading(true);
        break;
      case "programsLoaded":
        this.#toggleProgramsLoading(false);
        break;
      case "observationsLoading":
        this.#toggleObservationsLoading(true);
        break;
      case "observationsLoaded":
        this.#toggleObservationsLoading(false);
        break;
      case "showNoPrograms":
        this.#showNoPrograms();
        break;
      case "showNoObservations":
        this.#showNoObservations();
        break;
      case "toggleButtonToolbar":
        this.#toggleButtonToolbar(parameter.disabled);
        break;
    }
  }

  /**
   * Register controller callbacks for DOM events.
   * @param {String} event
   * @param {function()} handler
   */
  bindCallback(event, handler) {
    switch (event) {
      case "selectProgram":
        Utils.on(this.#programSelect, "change", (e) => {
          handler({ programId: e.target.value });
        });
        break;
      case "selectObservation":
        Utils.on(this.#observationSelect, "change", (e) => {
          handler({ observationId: e.target.value });
        });
        break;
      case "saveObservation":
        Utils.on(this.#saveButton, "click", (e) => {
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
    this.#view.bindCallback("selectProgram", (item) =>
      this.#selectProgram(item.programId)
    );
    this.#view.bindCallback("selectObservation", (item) =>
      this.#selectObservation(item.observationId)
    );
    this.#view.bindCallback("saveObservation", () => this.#saveObservation());
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
    if (programsList.length === 0) {
      this.#view.render("showNoPrograms");
    } else {
      this.#view.render("updatePrograms", { programs: programsList });
    }
    this.#view.render("programsLoaded");
  }

  /**
   * Fired when the user picks a program.
   * @private
   */
  async #selectProgram(programId) {
    this.#view.render("toggleButtonToolbar", { disabled: true });
    this.#view.render("observationsLoading");
    this.#view.render("resetAndClearObservationSelect");
    await this.#model.fetchObservations(programId);
    // Check if observations are available.
    const observationsList = this.#model.observationsList;
    if (observationsList.length === 0) {
      this.#view.render("showNoObservations");
    } else {
      this.#view.render("updateObservations", {
        observations: this.#model.observationsList,
      });
    }
    this.#view.render("observationsLoaded");
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

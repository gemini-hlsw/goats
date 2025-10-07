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
    formContainer.id = "observationFormContainer";
    container.append(row, Utils.createElement("hr"), formContainer);

    return container;
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
  #form = null;
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
    this.#formContainer = this.#container.querySelector(`#observationFormContainer`);
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

  #updateNormalObservation(observation) {
    this.#form = new ObservationForm(this.#formContainer, {
      observation: observation,
      mode: "normal",
      readOnly: false,
    });
  }

  #updateTooObservation(observation) {
    this.#form = new ObservationForm(this.#formContainer, {
      observation: observation,
      mode: "too",
      readOnly: false,
    });
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
    this.#form = new ObservationForm(this.#formContainer, {
      observation: observation,
      mode: "too",
      readOnly: false,
    });
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
      case "updateNormalObservation":
        this.#updateNormalObservation(parameter.observation);
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
      case "updateTooObservation":
        this.#updateTooObservation(parameter.observation);
        break;

      // Form renders.
      case "clearObservationForm":
        this.#clearObservationForm();
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
        this.#poPanel.onProgramSelect((id) => handler({ programId: id }));
        break;
      case "selectNormalObservation":
        this.#poPanel.onNormalSelect((id) => handler({ observationId: id }));
        break;
      case "selectTooObservation":
        this.#poPanel.onTooSelect((id) => handler({ observationId: id }));
        break;
      case "editObservation":
        this.#poPanel.onEdit(handler);
        break;
      case "saveObservation":
        this.#poPanel.onSave(handler);
        break;
      case "createNewObservation":
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
    // Program callbacks.
    this.#view.bindCallback("selectProgram", (item) =>
      this.#selectProgram(item.programId)
    );

    // Normal observation callbacks.
    this.#view.bindCallback("selectNormalObservation", (item) => {
      this.#selectNormalObservation(item.observationId);
    });
    this.#view.bindCallback("editObservation", () => {
      console.log("Controller got the edit observation.");
    });
    this.#view.bindCallback("saveObservation", () => this.#saveObservation());

    // ToO observation callbacks.
    this.#view.bindCallback("selectTooObservation", (item) => {
      this.#selectTooObservation(item.observationId);
    });
    // FIXME:
    // Which one below do I keep in callbacks?
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

  #selectNormalObservation(observationId) {
    this.#view.render("clearObservationForm");
    const observation = this.#model.getNormalObservation(observationId);
    this.#view.render("updateNormalObservation", { observation });
  }

  #selectTooObservation(observationId) {
    this.#view.render("clearObservationForm");
    const observation = this.#model.getTooObservation(observationId);
    this.#view.render("updateTooObservation", { observation });
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

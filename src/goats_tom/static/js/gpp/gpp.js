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
  #gppSaveNormalObservationUrl = `${this.#gppObservationsUrl}save-only/`;
  #gppCreateTooObservationUrl = `${this.#gppObservationsUrl}create-and-save/`;
  #gppUpdateNormalObservationUrl = `${this.#gppObservationsUrl}update-only/`;
  #gppPingUrl = `${this.#gppUrl}ping/`;

  // Data-storing maps.
  #normalObservations = new Map();
  #tooObservations = new Map();
  #programs = new Map();
  #activeObservation;
  #activeProgram;

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
    this.#activeProgram = null;
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
   * Creates a new ToO observation.
   * @param {*} formData The form data to submit.
   * @returns {Promise<{status: number, data: Object}>} A response object with status code and
   * response data.
   */
  async createTooObservation(formData) {
    // Append the target ID to the form data.
    formData.append("hiddenGoatsTargetIdInput", this.#targetId);
    return await this.#normalizeResponse(() =>
      this.#api.post(this.#gppCreateTooObservationUrl, formData, {}, false)
    );
  }

  /**
   * Normalize an API call into a consistent structure.
   * @param {() => Promise<any>} requestFn - A function that executes the request.
   * @returns {Promise<{ status: number, data: Object }>}
   */
  async #normalizeResponse(requestFn) {
    try {
      const data = await requestFn();
      return { status: 200, data };
    } catch (error) {
      return await this.#normalizeError(error);
    }
  }

  /**
   * Normalize an error response from fetch or API post/get call.
   * @param {Response|any} error - The error object thrown.
   * @returns {Promise<{ status: number, data: Object }>}
   */
  async #normalizeError(error) {
    if (error instanceof Response) {
      try {
        const contentType = error.headers.get("Content-Type") || "";
        const data = contentType.includes("application/json")
          ? await error.json()
          : { message: await error.text() };

        return { status: error.status, data };
      } catch {
        return {
          status: error.status,
          data: { message: "Failed to parse error response." },
        };
      }
    }

    // Non-HTTP errors
    return { status: 0, data: { message: String(error) } };
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
   * Updates on GPP a normal observation for the current target.
   *
   * @async
   * @param {FormData} formData - The form data containing observation details.
   * @returns {Promise<Object>} The normalized response from the API.
   */
  async updateOnGppNormalObservation(formData) {
    // Append the target ID to the form data.
    formData.append("hiddenGoatsTargetIdInput", this.#targetId);
    return await this.#normalizeResponse(() =>
      this.#api.post(this.#gppUpdateNormalObservationUrl, formData, {}, false)
    );
  }

  async saveNormalObservation(formData) {
    // Append the target ID to the form data.
    formData.append("hiddenGoatsTargetIdInput", this.#targetId);
    return await this.#normalizeResponse(() =>
      this.#api.post(this.#gppSaveNormalObservationUrl, formData, {}, false)
    );
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
   * Get a program object that is already in the cache. Also sets the active
   * program to track the last retrieved.
   * @param {string} programId
   * @returns {Object|undefined}
   */
  getProgram(programId) {
    const program = this.#programs.get(programId);
    this.#activeProgram = program || null;
    return program;
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
   * The last retrieved program from cache.
   * @returns {Object|null}
   */
  get activeProgram() {
    return this.#activeProgram;
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

  /**
   * Update the observation form with a normal observation.
   * @param {Object} observation
   * @private
   */
  #updateNormalObservation(observation) {
    this.#form = new ObservationForm(this.#formContainer, {
      observation: observation,
      mode: "normal",
      readOnly: false,
    });
  }

  /**
   * Update the observation form with a ToO observation.
   * @param {Object} observation
   * @private
   */
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
   * Get the data from the observation form.
   * @return {Object|null} The form data, or null if no form is present.
   * @private
   */
  #getFormData() {
    if (this.#form) {
      const formData = this.#form.getData();
      return formData;
    }
    return null;
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

      // Observation helpers.
      case "disableObservationButtons":
        this.#poPanel.toggleAllButtons(true);
        break;
      case "enableObservationButtons":
        this.#poPanel.toggleAllButtons(false);
        break;

      // Form renders.
      case "clearObservationForm":
        this.#clearObservationForm();
        break;
      case "getFormData":
        return this.#getFormData();

      default:
        console.warn(`[GPPView] Unknown render command: ${viewCmd}`);
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
      case "updateObservation":
        this.#poPanel.onUpdate(handler);
        break;
      case "saveObservation":
        this.#poPanel.onSave(handler);
        break;
      case "createAndSaveTooObservation":
        this.#poPanel.onCreateNew(handler);
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
  #modal;
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
    this.#modal = options.modal;

    // Bind the callbacks.
    // Program callbacks.
    this.#view.bindCallback("selectProgram", (item) =>
      this.#selectProgram(item.programId)
    );

    // Normal observation callbacks.
    this.#view.bindCallback("selectNormalObservation", (item) => {
      this.#selectNormalObservation(item.observationId);
    });
    this.#view.bindCallback("updateObservation", () => {
      this.#updateOnGppNormalObservation();
    });
    this.#view.bindCallback("saveObservation", () => this.#saveObservation());

    // ToO observation callbacks.
    this.#view.bindCallback("selectTooObservation", (item) => {
      this.#selectTooObservation(item.observationId);
    });
    this.#view.bindCallback("createAndSaveTooObservation", () =>
      this.#createAndSaveTooObservation()
    );
  }

  /**
   * Updates a normal observation in GPP.
   * Shows progress and result modals, and refreshes the observations list.
   * @returns {Promise<void>}
   * @private
   */
  async #updateOnGppNormalObservation() {
    const formData = this.#view.render("getFormData");

    if (formData == null) {
      this.#showMissingFormModal(
        "Missing Form Data",
        "No form data available to update on GPP and save an observation."
      );
      // Don't refresh observations or disable buttons, just return.
      return;
    }

    // Show progress modal with spinner and message.
    this.#showProgressModal(
      "Updating Observation",
      "Please wait while your observation is updated in GPP."
    );

    // Attempt to update the normal observation.
    const { status, data } = await this.#model.updateOnGppNormalObservation(formData);

    this.#handleObservationResponse(
      "Observation Updated on GPP",
      status,
      data,
      "Observation Update Result"
    );

    // Finally, refresh the observations list.
    const programId = this.#model.activeProgram.id;
    await this.#resetAndUpdateObservations(programId);
  }

  /**
   * Creates and saves a new ToO observation.
   * Uses ModalManager to show progress and results.
   * @returns {Promise<void>} A promise that resolves when the operation is complete.
   * @private
   */
  async #createAndSaveTooObservation() {
    const formData = this.#view.render("getFormData");

    if (formData == null) {
      this.#showMissingFormModal(
        "Missing Form Data",
        "No form data available to create a new observation."
      );
      // Don't refresh observations or disable buttons, just return.
      return;
    }

    // Show progress modal with spinner and message.
    this.#showProgressModal(
      "Creating Observation",
      "Please wait while your observation is created in GPP and added to GOATS."
    );

    // Attempt to create the ToO observation.
    const { status, data } = await this.#model.createTooObservation(formData);

    this.#handleObservationResponse(
      "Observation Created and Saved",
      status,
      data,
      "Observation Creation and Saved Result"
    );

    // Finally, refresh the observations list.
    const programId = this.#model.activeProgram.id;
    await this.#resetAndUpdateObservations(programId);
  }

  /**
   * Handles the response from an observation creation or update request.
   * Updates the modal with appropriate messages based on the response status and data.
   * @param {string} titleSuccess - Title to display on success.
   * @param {number} status - HTTP status code from the response.
   * @param {Object} data - Response data object, may contain messages.
   * @param {string} fallbackTitle - Title to display on failure or unexpected result.
   * @param {?string} [id=null] - Optional observation ID to display.
   * @returns {void}
   * @private
   */
  #handleObservationResponse(titleSuccess, status, data, fallbackTitle, id = null) {
    const isStructured = data?.messages && Array.isArray(data.messages);

    if (status >= 200 && status < 300 && isStructured) {
      this.#modal.update({
        title: titleSuccess,
        body: `
        <div class="text-center">
          <p class="fst-italic">Your observation has been successfully processed.</p>
          ${id ? `<p><strong>Observation ID:</strong> ${id}</p>` : ""}
          ${this.renderMessageTable(data.messages)}
        </div>
      `,
      });
    } else if (status >= 200 && status < 300) {
      this.#modal.update({
        title: titleSuccess,
        body: `
        <div class="text-center">
          <p class="fst-italic">The operation succeeded, but the response format was unexpected.</p>
          <pre class="bg-light p-3 rounded small text-wrap">
            <code>${JSON.stringify(data, null, 2)}</code>
          </pre>
        </div>
      `,
      });
    } else if (isStructured) {
      this.#modal.update({
        title: fallbackTitle,
        body: `
        <div class="text-center">
          <p>The request was processed with status: ${data.status}.</p>
          ${id ? `<p><strong>Observation ID:</strong> ${id}</p>` : ""}
          ${this.renderMessageTable(data.messages)}
        </div>
      `,
      });
    } else {
      this.#modal.update({
        title: `Request Failed (${status})`,
        body: `
        <div class="text-center">
          <p class="fst-italic">An error occurred.</p>
          <pre class="bg-light p-3 rounded small text-wrap">
            <code>${JSON.stringify(data, null, 2)}</code>
          </pre>
        </div>
      `,
      });
    }
  }

  /**
   * Shows a modal indicating that the observation form is missing or incomplete.
   * @param {string} title - The title to display in the modal.
   * @param {string} subtitle - The subtitle to display in the modal.
   * @returns {void}
   * @private
   */
  #showMissingFormModal(title, subtitle) {
    this.#modal.show({
      title,
      body: `
      <div class="text-center">
        <p class="fst-italic">${subtitle}</p>
        <p>Please fill out the observation form before submitting.</p>
      </div>
    `,
      backdrop: "static",
      dialogClasses: ["modal-dialog-centered", "modal-dialog-scrollable", "modal-lg"],
    });
  }

  /**
   * Shows a modal dialog indicating that a process is in progress.
   * @private
   * @param {string} title - The title to display in the modal.
   * @param {string} subtitle - The subtitle or message to display below the spinner.
   * @returns {void}
   */
  #showProgressModal(title, subtitle) {
    this.#modal.show({
      title,
      body: `
      <div class="text-center">
        <div class="spinner-border mb-4" role="status">
          <span class="visually-hidden">Loading...</span>
        </div>
        <p class="fst-italic">${subtitle}</p>
        <p>This process can take a few minutes. Do not refresh the page, close this modal, or use the back or forward buttons until the operation completes.</p>
      </div>
    `,
      backdrop: "static",
      dialogClasses: ["modal-dialog-centered", "modal-dialog-scrollable", "modal-lg"],
    });
  }

  /**
   * Renders a status message table from a list of messages.
   * @param {Array<Object>} messages - The messages array with `stage`, `status`, and `message`.
   * @returns {string} - HTML string for the table.
   */
  renderMessageTable(messages) {
    const rows = messages
      .map(({ stage, status, message }, index) => {
        let variant = "table-";
        switch (status.toLowerCase()) {
          case "success":
            variant += "success";
            break;
          case "error":
            variant += "danger";
            break;
          case "warning":
            variant += "warning";
            break;
          default:
            variant += "secondary";
            break;
        }

        return `
        <tr class="${variant}">
          <td class="text-end">${index + 1}.</td>
          <td class="text-start">${stage}</td>
          <td>${status}</td>
          <td class="text-start">${message}</td>
        </tr>`;
      })
      .join("");

    return `
    <div class="table-responsive">
      <table class="table table-striped">
        <thead class="table-secondary">
          <tr>
            <th class="text-end" scope="col"></th>
            <th class="text-start" scope="col">Stage</th>
            <th scope="col">Status</th>
            <th class="text-start" scope="col">Message</th>
          </tr>
        </thead>
        <tbody class="table-group-divider">
          ${rows}
        </tbody>
      </table>
    </div>
  `;
  }

  /**
   * Resets and updates both normal and ToO observation lists for the given program ID.
   * @param {string} programId  Program identifier.
   * @returns {Promise<void>}
   * @private
   */
  async #resetAndUpdateObservations(programId) {
    this.#view.render("disableObservationButtons");

    // Reset the observation lists.
    this.#view.render("resetNormalObservations");
    this.#view.render("resetTooObservations");

    // Show loading states.
    this.#view.render("normalObservationsLoading");
    this.#view.render("tooObservationsLoading");

    // Fetch observations again.
    await this.#model.fetchObservations(programId);

    // Update both lists in one go.
    this.#view.render("updateNormalObservations", {
      observations: this.#model.normalObservationsList,
    });
    this.#view.render("updateTooObservations", {
      observations: this.#model.tooObservationsList,
    });

    // Remove loading states.
    this.#view.render("normalObservationsLoaded");
    this.#view.render("tooObservationsLoaded");
  }

  async #saveObservation() {
    // const observation = this.#model.activeObservation;

    const formData = this.#view.render("getFormData");

    if (formData == null) {
      this.#showMissingFormModal(
        "Missing Form Data",
        "No form data available to save observation to GOATS."
      );
      // Don't refresh observations or disable buttons, just return.
      return;
    }

    // Show progress modal with spinner and message.
    this.#showProgressModal(
      "Saving Observation to GOATS",
      "Please wait while your observation is added to GOATS."
    );

    // Attempt to save the observation.
    const { status, data } = await this.#model.saveNormalObservation(formData);

    this.#handleObservationResponse(
      "Observation Saved to GOATS",
      status,
      data,
      "Observation Result"
    );

    // Finally, refresh the observations list.
    const programId = this.#model.activeProgram.id;
    await this.#resetAndUpdateObservations(programId);
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
   */
  async #selectProgram(programId) {
    // Set the active program in the model.
    this.#model.getProgram(programId);
    await this.#resetAndUpdateObservations(programId);
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
      modal: window.modal,
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

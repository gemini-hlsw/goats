/**
 * ProgramObservationsPanel: builds and manages Program + Observations + ToO UI.
 * Handles <select> dropdowns, loading spinners, and button toolbars.
 *
 * Usage:
 *   const panel = new ProgramObservationsPanel(parentElement, { debug: true });
 *   panel.onProgramSelect(id => console.log("Program changed:", id));
 *
 * @class
 */
class ProgramObservationsPanel {
  #container;
  #parentElement;
  #debug;

  #programSelect;
  #programSpinner;

  #normalSelect;
  #normalSpinner;
  #obsToolbar;
  #updateButton;
  #saveButton;

  #tooSelect;
  #tooSpinner;
  #tooToolbar;
  #createNewButton;

  /**
   * Construct a new ProgramObservationsPanel and attach it to the DOM.
   *
   * @param {!HTMLElement} parentElement - Parent DOM node to which this panel will be appended.
   * @param {{debug?: boolean}=} [options] - Optional settings.
   *   - debug: if true, logs state changes and event activity.
   */
  constructor(parentElement, { debug = false } = {}) {
    this.#parentElement = parentElement;
    this.#debug = debug;

    this.#container = this.#create();
    this.#parentElement.appendChild(this.#container);

    this.#programSelect = this.#container.querySelector("#programSelect");
    this.#programSpinner = this.#container.querySelector("#programLoading");

    this.#normalSelect = this.#container.querySelector("#normalObservationSelect");
    this.#normalSpinner = this.#container.querySelector("#normalObservationLoading");
    this.#obsToolbar = this.#container.querySelector("#obsButtonToolbar");
    this.#updateButton = this.#obsToolbar.querySelector("#updateButton");
    this.#saveButton = this.#obsToolbar.querySelector("#saveButton");

    this.#tooSelect = this.#container.querySelector("#tooObservationSelect");
    this.#tooSpinner = this.#container.querySelector("#tooObservationLoading");
    this.#tooToolbar = this.#container.querySelector("#tooButtonToolbar");
    this.#createNewButton = this.#tooToolbar.querySelector("#createNewButton");

    // Initial state: disable observations and buttons.
    this.toggleNormalSelect(true);
    this.toggleTooSelect(true);
    this.toggleNormalButtons(true);
    this.toggleTooButtons(true);

    if (this.#debug) console.log("[ProgramObservationsPanel] Initialized and mounted.");
  }

  /**
   * Get the root container for attaching to DOM.
   * @returns {!HTMLElement}
   */
  get element() {
    return this.#container;
  }

  /**
   * Enable or disable debug logging at runtime.
   * @param {boolean} flag
   */
  setDebug(flag) {
    this.#debug = flag;
    if (this.#debug) console.log("[ProgramObservationsPanel] Debug logging enabled.");
  }

  /**
   * Clear and show an "empty" option message in a given select element.
   * @private
   * @param {!HTMLSelectElement} selectEl
   */
  #showEmpty(selectEl) {
    const option = Utils.createElement("option");
    option.value = "None";
    option.textContent = "None available";
    option.disabled = true;
    selectEl.appendChild(option);

    if (this.#debug)
      console.log(
        "[ProgramObservationsPanel] Empty state shown for select:",
        selectEl.id
      );
  }

  /**
   * Reset the ToO select back to just its placeholder.
   * Does not remove existing placeholder.
   */
  clearTooSelect() {
    this.#tooSelect.length = 1;
    if (this.#debug) console.log("[ProgramObservationsPanel] Cleared ToO select.");
  }

  /**
   * Reset the normal select back to just its placeholder.
   * Does not remove existing placeholder.
   */
  clearNormalSelect() {
    this.#normalSelect.length = 1;
    if (this.#debug) console.log("[ProgramObservationsPanel] Cleared normal select.");
  }

  /**
   * Populate the program <select>.
   * @param {!Array<Object>} programs - Array of program objects.
   */
  updatePrograms(programs) {
    this.#fillSelect(this.#programSelect, programs);
  }

  /**
   * Populate the normal observations <select>.
   * @param {!Array<Object>} observations - Array of observation objects.
   */
  updateNormalObservations(observations) {
    this.#fillSelect(this.#normalSelect, observations);
  }

  /**
   * Populate the ToO observations <select>.
   * @param {!Array<Object>} observations - Array of observation objects.
   */
  updateTooObservations(observations) {
    this.#fillSelect(this.#tooSelect, observations);
  }

  /**
   * Show or hide loading state for programs.
   * @param {boolean} isLoading
   */
  toggleProgramsLoading(isLoading) {
    this.#programSelect.disabled = isLoading;
    this.#programSpinner.hidden = !isLoading;
    if (this.#debug)
      console.log("[ProgramObservationsPanel] Program loading:", isLoading);
  }

  /**
   * Show or hide loading state for normal observations.
   * @param {boolean} isLoading
   */
  toggleNormalLoading(isLoading) {
    this.#normalSelect.disabled = isLoading;
    this.#normalSpinner.hidden = !isLoading;
    if (this.#debug)
      console.log("[ProgramObservationsPanel] Normal loading:", isLoading);
  }

  /**
   * Show or hide loading state for ToO observations.
   * @param {boolean} isLoading
   */
  toggleTooLoading(isLoading) {
    this.#tooSelect.disabled = isLoading;
    this.#tooSpinner.hidden = !isLoading;
    if (this.#debug) console.log("[ProgramObservationsPanel] ToO loading:", isLoading);
  }

  /**
   * Enable or disable the normal observation toolbar buttons.
   * @param {boolean} disabled
   */
  toggleNormalButtons(disabled) {
    this.#updateButton.disabled = disabled;
    this.#saveButton.disabled = disabled;
    if (this.#debug)
      console.log("[ProgramObservationsPanel] Normal buttons disabled:", disabled);
  }

  toggleNormalSelect(disabled) {
    this.#normalSelect.disabled = disabled;
    if (this.#debug)
      console.log("[ProgramObservationsPanel] Normal select disabled:", disabled);
  }

  toggleTooSelect(disabled) {
    this.#tooSelect.disabled = disabled;
    if (this.#debug)
      console.log("[ProgramObservationsPanel] ToO select disabled:", disabled);
  }

  /**
   * Enable or disable the ToO toolbar buttons.
   * @param {boolean} disabled
   */
  toggleTooButtons(disabled) {
    this.#createNewButton.disabled = disabled;
    if (this.#debug)
      console.log("[ProgramObservationsPanel] ToO buttons disabled:", disabled);
  }

  // Event hooks.

  /**
   * Attach a handler for when a program is selected.
   * Resets observations state (clears selects + disables buttons).
   * @param {function(string):void} handler - Callback with program ID.
   */
  onProgramSelect(handler) {
    this.#programSelect.addEventListener("change", (e) => {
      if (this.#debug)
        console.log("[ProgramObservationsPanel] Program selected:", e.target.value);

      // Reset dependent state.
      this.clearNormalSelect();
      this.clearTooSelect();
      this.toggleNormalSelect(true);
      this.toggleTooSelect(true);
      this.toggleNormalButtons(true);
      this.toggleTooButtons(true);

      handler(e.target.value);
    });
  }

  /**
   * Attach a handler for when a normal observation is selected.
   * Also enforces state rules (enable normal, disable ToO).
   * @param {function(string):void} handler - Callback with observation ID.
   */
  onNormalSelect(handler) {
    this.#normalSelect.addEventListener("change", (e) => {
      if (this.#debug)
        console.log("[ProgramObservationsPanel] Normal selected:", e.target.value);

      // Enable normal buttons, disable ToO buttons.
      this.toggleNormalButtons(false);
      this.toggleTooButtons(true);

      // Reset tooSelect back to placeholder without clearing options.
      this.#tooSelect.selectedIndex = 0;

      handler(e.target.value);
    });
  }

  /**
   * Attach a handler for when a ToO observation is selected.
   * Also enforces state rules (enable ToO, disable normal).
   * @param {function(string):void} handler - Callback with observation ID.
   */
  onTooSelect(handler) {
    this.#tooSelect.addEventListener("change", (e) => {
      if (this.#debug)
        console.log("[ProgramObservationsPanel] ToO selected:", e.target.value);

      // Enable ToO buttons, disable normal buttons.
      this.toggleTooButtons(false);
      this.toggleNormalButtons(true);

      // Reset normalSelect back to placeholder without clearing options.
      this.#normalSelect.selectedIndex = 0;

      handler(e.target.value);
    });
  }

  /**
   * Attach a handler for the "Save" button.
   * @param {function():void} handler
   */
  onSave(handler) {
    this.#saveButton.addEventListener("click", () => {
      if (this.#debug) console.log("[ProgramObservationsPanel] Save clicked");
      handler();
    });
  }

  /**
   * Attach a handler for the "Update" button.
   * @param {function():void} handler
   */
  onUpdate(handler) {
    this.#updateButton.addEventListener("click", () => {
      if (this.#debug) console.log("[ProgramObservationsPanel] Update clicked");
      handler();
    });
  }

  /**
   * Attach a handler for the "Create New Observation" button.
   * @param {function():void} handler
   */
  onCreateNew(handler) {
    this.#createNewButton.addEventListener("click", () => {
      if (this.#debug) console.log("[ProgramObservationsPanel] Create New clicked");
      handler();
    });
  }

  // DOM building methods.

  /**
   * Build the panel DOM structure.
   * @private
   * @returns {!HTMLElement}
   */
  #create() {
    const row = Utils.createElement("div", ["row", "g-3"]);
    const colProgram = Utils.createElement("div", ["col-12"]);
    const colNormal = Utils.createElement("div", ["col-lg-6"]);
    const colToo = Utils.createElement("div", ["col-lg-6"]);

    // Program block.
    colProgram.append(
      this.#createSelectWithSpinner("program", "Active Programs", "Choose a program...")
    );

    // Normal obs block.
    colNormal.append(
      this.#createSelectWithSpinner(
        "normalObservation",
        "Active Observations",
        "Choose an observation..."
      ),
      this.#createToolbar("obsButtonToolbar", [
        { id: "updateButton", label: "Update On GPP & Save", color: "primary", classes: ["me-2"] },
        { id: "saveButton", label: "Save", color: "primary" },
      ])
    );

    // ToO block.
    colToo.append(
      this.#createSelectWithSpinner(
        "tooObservation",
        "Approved ToO Configurations",
        "Choose a ToO configuration..."
      ),
      this.#createToolbar("tooButtonToolbar", [
        { id: "createNewButton", label: "Create On GPP & Save", color: "primary" },
      ])
    );

    row.append(colProgram, colNormal, colToo);
    return row;
  }

  /**
   * Generates a `<select>` populated with a hidden placeholder option.
   * @param {string} id  Prefix for the element ID.
   * @param {string} labelText The text for the label.
   * @param {string} optionHint  Placeholder text.
   * @returns {!HTMLSelectElement}
   * @private
   */
  #createSelectWithSpinner(id, labelText, optionHint) {
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
   * Creates a toolbar containing one or more buttons.
   * @private
   * @param {string} toolbarId - ID to assign to the toolbar container element.
   * @param actions - Array of action definitions. Each defines one button to render.
   * @returns {!HTMLDivElement} The toolbar element containing the generated buttons.
   */
  #createToolbar(toolbarId, actions) {
    const toolbar = Utils.createElement("div", ["mt-2"]);
    toolbar.id = toolbarId;

    actions.forEach(({ id, label, color, classes = [] }) => {
      const btn = Utils.createElement("button", ["btn", `btn-${color}`, ...classes]);
      btn.id = id;
      btn.textContent = label;
      btn.type = "button";
      toolbar.append(btn);
    });

    return toolbar;
  }

  /**
   * Fill a <select> with options.
   * @private
   * @param {!HTMLSelectElement} selectEl
   * @param {!Array<Object>} options
   */
  #fillSelect(selectEl, options) {
    // Clear existing options, keep placeholder.
    selectEl.length = 1;

    // If no options, show "None available" option.
    if (!options || options.length === 0) {
      this.#showEmpty(selectEl);
      return;
    }
    const frag = document.createDocumentFragment();
    options.forEach((o) => {
      const opt = Utils.createElement("option");
      opt.value = o.id;
      opt.textContent = `${o.id} - ${o.name ?? o.title ?? ""}`;
      frag.appendChild(opt);
    });
    selectEl.appendChild(frag);
    selectEl.disabled = false;
    if (this.#debug)
      console.log(
        "[ProgramObservationsPanel] Filled select:",
        selectEl.id,
        "with",
        options.length,
        "items."
      );
  }
}

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
  #debugTag = "[ProgramObservationsPanel]";
  #programSelect;
  #programSpinner;
  #normalSelect;
  #normalSpinner;
  #obsToolbar;
  #updateButton;
  #saveButton;
  #tooSelect;
  #tomSelects = new Map();
  #tooConfigurations = new Map();
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
    this.#normalSelect = this.#container.querySelector(
      "#normalObservationSelect",
    );
    this.#normalSpinner = this.#container.querySelector(
      "#normalObservationLoading",
    );
    this.#obsToolbar = this.#container.querySelector("#obsButtonToolbar");
    this.#updateButton = this.#obsToolbar.querySelector("#updateButton");
    this.#saveButton = this.#obsToolbar.querySelector("#saveButton");
    this.#tooSelect = this.#container.querySelector("#tooObservationSelect");
    // The list a native select opens is the browser's and takes no styling, so
    // Tom Select draws all three, as GOATS menus. The ToO options also carry
    // their configuration's details.
    this.#mountTomSelect(this.#programSelect);
    this.#mountTomSelect(this.#normalSelect);
    this.#mountTomSelect(this.#tooSelect, {
      render: { option: (data, escape) => this.#renderTooOption(data, escape) },
    });
    this.#tooSpinner = this.#container.querySelector("#tooObservationLoading");
    this.#tooToolbar = this.#container.querySelector("#tooButtonToolbar");
    this.#createNewButton = this.#tooToolbar.querySelector("#createNewButton");
    // Initial state: disable observations and buttons.
    this.toggleNormalSelect(true);
    this.toggleTooSelect(true);
    this.toggleNormalButtons(true);
    this.toggleTooButtons(true);
    this.#logDebug("Initialized and mounted.");
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
    this.#logDebug(`Setting debug to ${flag}`);
  }
  /**
   * Logs a debug message if debugging is enabled.
   *
   * @param {string} message - The message to log.
   * @private
   */
  #logDebug(message) {
    if (this.#debug) console.debug(`${this.#debugTag} ${message}`);
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
    this.#logDebug(`Empty state shown for select: ${selectEl.id}`);
  }
  /**
   * Reset the ToO select back to just its placeholder.
   * Does not remove existing placeholder.
   */
  clearTooSelect() {
    this.#tooSelect.length = 1;
    this.#syncSelect(this.#tooSelect);
    this.#logDebug("Cleared ToO select.");
  }
  /**
   * Reset the normal select back to just its placeholder.
   * Does not remove existing placeholder.
   */
  clearNormalSelect() {
    // As #fillSelect does: its options sit in option groups.
    while (this.#normalSelect.options.length > 1) this.#normalSelect.remove(1);
    this.#syncSelect(this.#normalSelect);
    this.#logDebug("Cleared normal select.");
  }
  /**
   * Populate the program <select>.
   * @param {!Array<Object>} programs - Array of program objects.
   */
  updatePrograms(programs) {
    this.#fillSelect(this.#programSelect, programs, {
      // Use program reference label if available, else ID.
      getLabel: (p) => `${p.reference?.label ?? p.id} - ${p.name ?? p.title ?? ""}`,
    });
  }
  /**
   * Populate the observations <select>: the observations of the program, then
   * its calibrations under their own heading. ToO observations that are still
   * being prepared, with a region rather than a target, are not observations to
   * act on, so they are left out.
   * @param {!Array<Object>} observations - Array of observation objects.
   */
  updateNormalObservations(observations) {
    this.#fillSelect(
      this.#normalSelect,
      (observations ?? []).filter((o) => !o?.isToo),
      {
        groups: ["Calibrations"],
        getGroup: (o) => (o?.calibrationRole ? "Calibrations" : null),
      },
    );
  }
  /**
   * Populate the approved ToO configurations <select>.
   * @param {!Array<Object>} configurations - Array of configuration requests.
   * @param {!Map<string, !Array<string>>=} targets - Target names of each
   *     configuration, by ID.
   */
  updateTooConfigurations(configurations, targets = new Map()) {
    this.#tooConfigurations = new Map(
      (configurations ?? []).map((c) => [c.id, c]),
    );
    this.#fillSelect(this.#tooSelect, configurations, {
      getLabel: (c) =>
        ProgramObservationsPanel.configurationLabel(c, targets.get(c.id)),
    });
  }
  /**
   * Build a readable label for an approved configuration request, as the
   * observations select labels its own: its ID, then its target, "Multiple" if
   * it has several.
   * @param {!Object} configuration - Configuration request object.
   * @param {!Array<string>=} targets - Its target names.
   * @returns {string}
   */
  static configurationLabel(configuration, targets = []) {
    const target = targets.length > 1 ? "Multiple" : targets[0];
    return [configuration.id, target].filter(Boolean).join(" - ");
  }
  /**
   * The setup an approved configuration request approves, short as Explore
   * shows it: instrument, focal plane and grating.
   * @param {!Object} configuration - Configuration request object.
   * @returns {string}
   */
  static configurationSetup(configuration) {
    const mode = configuration?.configuration?.observingMode ?? {};
    // A grating goes by the name before its part number: R400_G5310 is the R400.
    const grating = mode.gmosNorthLongSlit?.grating ?? mode.gmosSouthLongSlit?.grating;
    return [
      Lookups.instrumentShortName[mode.instrument] ?? mode.instrument,
      Lookups.observingModeFpu[mode.mode],
      grating?.split("_")[0],
    ]
      .filter(Boolean)
      .join(" ");
  }
  /**
   * The summary of an approved configuration request, in Explore's order, as
   * `[label, value]` pairs: the region it covers, then the conditions it
   * approves. A partial arc reads as its range, as in Explore. Missing values
   * are left out.
   * @param {!Object} configuration - Configuration request object.
   * @returns {!Array<!Array<string>>}
   */
  static configurationSummary(configuration) {
    const conditions = configuration?.configuration?.conditions ?? {};
    const region = configuration?.configuration?.target?.region ?? {};
    // Labelled as the form labels them, so the two read the same.
    const condition = (name) =>
      conditions[name]
        ? (Lookups[name]?.[conditions[name]] ??
          Formatters.titleCaseFromUnderscore(conditions[name]))
        : "";
    // The form leaves the image quality unit to its label; here it goes with it.
    const iq = Lookups.imageQuality[conditions.imageQuality];
    // GPP pads the seconds with zeros: 10:00:00.000000 reads as 10:00:00.
    const sexagesimal = (text) => text.replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "");
    const arc = (a, notation) => {
      if (a?.type === "PARTIAL" && a.start?.[notation] && a.end?.[notation]) {
        return `${sexagesimal(a.start[notation])} - ${sexagesimal(a.end[notation])}`;
      }
      return a?.type ? Formatters.titleCaseFromUnderscore(a.type) : "";
    };

    return [
      ["RA", arc(region.rightAscensionArc, "hms")],
      ["Dec", arc(region.declinationArc, "dms")],
      ["IQ", iq ? `${iq} arcsec` : condition("imageQuality")],
      ["CC", condition("cloudExtinction")],
      ["SB", condition("skyBackground")],
      ["WV", condition("waterVapor")],
    ].filter(([, value]) => value);
  }
  /**
   * Render a ToO option: its label, then, always in view and smaller, the setup
   * of its configuration and the rest of its details. "None available" stands
   * for no configuration.
   * @param {!Object} data - Tom Select option data.
   * @param {function(string): string} escape - HTML escaper.
   * @returns {string}
   * @private
   */
  #renderTooOption(data, escape) {
    const configuration = this.#tooConfigurations.get(data.value);
    if (!configuration) return `<div>${escape(data.text)}</div>`;
    // A description list allows one div around each term and its detail. The
    // option's class tells its look apart from the one-line options'.
    const pairs = ProgramObservationsPanel.configurationSummary(configuration)
      .map(
        ([label, value]) =>
          '<div class="too-configuration-pair">' +
          `<dt>${escape(label)}</dt><dd>${escape(value)}</dd></div>`,
      )
      .join("");
    const setup = ProgramObservationsPanel.configurationSetup(configuration);
    return (
      '<div class="too-configuration-option">' +
      `<div class="too-configuration-label">${escape(data.text)}</div>` +
      `<div class="too-configuration-setup">${escape(setup)}</div>` +
      `<dl class="too-configuration-summary">${pairs}</dl></div>`
    );
  }
  /**
   * Draw a native <select> with Tom Select, read-only, so it picks like a native
   * select, without a search box.
   * @param {!HTMLSelectElement} select - The native select.
   * @param {!Object=} settings - Tom Select settings on top of the shared ones.
   * @private
   */
  #mountTomSelect(select, settings = {}) {
    const tomSelect = new TomSelect(select, {
      maxOptions: null,
      controlInput: '<input type="text" autocomplete="off" size="1" readonly />',
      ...settings,
    });
    this.#tomSelects.set(select, tomSelect);
  }
  /**
   * Mirror a native <select> into its Tom Select widget, which keeps its own
   * copy of the options, the selection and the disabled state. Called whenever
   * the native select changes.
   * @param {!HTMLSelectElement} select - The native select.
   * @private
   */
  #syncSelect(select) {
    const tomSelect = this.#tomSelects.get(select);
    // Sync only adds options, so drop the current ones first.
    tomSelect.clear(true);
    tomSelect.clearOptions();
    tomSelect.sync();
    if (select.disabled) {
      tomSelect.disable();
    } else {
      tomSelect.enable();
    }
  }
  /**
   * Show or hide loading state for programs.
   * @param {boolean} isLoading
   */
  toggleProgramsLoading(isLoading) {
    this.#programSelect.disabled = isLoading;
    this.#syncSelect(this.#programSelect);
    this.#programSpinner.hidden = !isLoading;
    this.#logDebug(`Program loading: ${isLoading}`);
  }
  /**
   * Show or hide loading state for normal observations.
   * @param {boolean} isLoading
   */
  toggleNormalLoading(isLoading) {
    this.#normalSelect.disabled = isLoading;
    this.#syncSelect(this.#normalSelect);
    this.#normalSpinner.hidden = !isLoading;
    this.#logDebug(`Normal loading: ${isLoading}`);
  }
  /**
   * Show or hide loading state for ToO observations.
   * @param {boolean} isLoading
   */
  toggleTooLoading(isLoading) {
    this.#tooSelect.disabled = isLoading;
    this.#syncSelect(this.#tooSelect);
    this.#tooSpinner.hidden = !isLoading;
    this.#logDebug(`ToO loading: ${isLoading}`);
  }
  /**
   * Enable or disable the normal observation toolbar buttons.
   * @param {boolean} disabled
   */
  toggleNormalButtons(disabled) {
    this.#updateButton.disabled = disabled;
    this.#saveButton.disabled = disabled;
    this.#logDebug(`Normal buttons disabled: ${disabled}`);
  }
  /**
   * Enable or disable the normal observation <select>.
   * @param {boolean} disabled
   */
  toggleNormalSelect(disabled) {
    this.#normalSelect.disabled = disabled;
    this.#syncSelect(this.#normalSelect);
    this.#logDebug(`Normal select disabled: ${disabled}`);
  }
  /**
   * Enable or disable the ToO observation <select>.
   * @param {boolean} disabled
   */
  toggleTooSelect(disabled) {
    this.#tooSelect.disabled = disabled;
    this.#syncSelect(this.#tooSelect);
    this.#logDebug(`ToO select disabled: ${disabled}`);
  }
  /**
   * Enable or disable only the Update button.
   * @param {boolean} disabled
   */
  toggleUpdateButton(disabled) {
    this.#updateButton.disabled = disabled;
    this.#logDebug(`Update button disabled: ${disabled}`);
  }
  /**
   * Enable or disable the ToO toolbar buttons.
   * @param {boolean} disabled
   */
  toggleTooButtons(disabled) {
    this.#createNewButton.disabled = disabled;
    this.#logDebug(`ToO buttons disabled: ${disabled}`);
  }
  /**
   * Enable or disable all observation toolbar buttons.
   * @param {boolean} disabled
   */
  toggleAllButtons(disabled) {
    this.toggleNormalButtons(disabled);
    this.toggleTooButtons(disabled);
    this.#logDebug(`All buttons disabled: ${disabled}`);
  }
  // Event hooks.
  /**
   * Attach a handler for when a program is selected.
   * Resets observations state (clears selects + disables buttons).
   * @param {function(string):void} handler - Callback with program ID.
   */
  onProgramSelect(handler) {
    this.#programSelect.addEventListener("change", (e) => {
      this.#logDebug(`Program selected: ${e.target.value}`);
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
      this.#logDebug(`Normal selected: ${e.target.value}`);
      this.toggleNormalButtons(false);
      this.toggleTooButtons(true);
      // Reset tooSelect back to placeholder without clearing options.
      this.#tooSelect.selectedIndex = 0;
      this.#syncSelect(this.#tooSelect);
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
      this.#logDebug(`ToO selected: ${e.target.value}`);
      // Enable ToO buttons, disable normal buttons.
      this.toggleTooButtons(false);
      this.toggleNormalButtons(true);
      // Reset normalSelect back to placeholder without clearing options.
      this.#normalSelect.selectedIndex = 0;
      this.#syncSelect(this.#normalSelect);
      handler(e.target.value);
    });
  }
  /**
   * Attach a handler for the "Save" button.
   * @param {function():void} handler
   */
  onSave(handler) {
    this.#saveButton.addEventListener("click", () => {
      this.#logDebug("Save clicked");
      handler();
    });
  }
  /**
   * Attach a handler for the "Update" button.
   * @param {function():void} handler
   */
  onUpdate(handler) {
    this.#updateButton.addEventListener("click", () => {
      this.#logDebug("Update clicked");
      handler();
    });
  }
  /**
   * Attach a handler for the "Create New Observation" button.
   * @param {function():void} handler
   */
  onCreateNew(handler) {
    this.#createNewButton.addEventListener("click", () => {
      this.#logDebug("Create New clicked");
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
      this.#createSelectWithSpinner(
        "program",
        "Active Programs",
        "Choose a program...",
      ),
    );
    // Normal obs block.
    colNormal.append(
      this.#createSelectWithSpinner(
        "normalObservation",
        "Active Observations",
        "Choose an observation...",
      ),
      this.#createToolbar("obsButtonToolbar", [
        {
          id: "updateButton",
          label: "Update On GPP",
          color: "primary",
          classes: ["me-2"],
        },
        { id: "saveButton", label: "Save To GOATS", color: "primary" },
      ]),
    );
    // ToO block.
    colToo.append(
      this.#createSelectWithSpinner(
        "tooObservation",
        "Approved ToO Configurations",
        "Choose a ToO configuration...",
      ),
      this.#createToolbar("tooButtonToolbar", [
        {
          id: "createNewButton",
          label: "Create On GPP & Save To GOATS",
          color: "primary",
        },
      ]),
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
      const btn = Utils.createElement("button", [
        "btn",
        `btn-${color}`,
        ...classes,
      ]);
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
   * @param {!HTMLSelectElement} selectEl - The select element to populate.
   * @param {!Array<Object>} options - Array of objects with `id` and `name` or `title` properties.
   * @param {Object} [opts] - Optional behaviour overrides.
   * @param {function(Object): string} [opts.getLabel] - Label resolver.
   * @param {function(Object): ?string} [opts.getGroup] - Resolver returning the
   *     <optgroup> an entry belongs to, or null to leave it ungrouped.
   * @param {!Array<string>} [opts.groups] - Group labels, in the order they are rendered.
   */
  #fillSelect(
    selectEl,
    options,
    {
      getLabel = (o) => `${o.id} - ${o.name ?? o.title ?? ""}`,
      getGroup = () => null,
      groups = [],
    } = {},
  ) {
    while (selectEl.options.length > 1) selectEl.remove(1);
    Array.from(selectEl.querySelectorAll("optgroup")).forEach((g) => g.remove());

    if (!options || options.length === 0) {
      this.#showEmpty(selectEl);
      this.#syncSelect(selectEl);
      return;
    }

    const frag = document.createDocumentFragment();
    const optgroups = new Map(
      groups.map((label) => {
        const group = document.createElement("optgroup");
        group.label = label;
        return [label, group];
      }),
    );

    options.forEach((o) => {
      const opt = Utils.createElement("option");
      opt.value = o.id;
      opt.textContent = getLabel(o);

      const group = optgroups.get(getGroup(o));
      if (group) {
        group.appendChild(opt);
      } else {
        frag.appendChild(opt);
      }
    });

    // Keep the requested group order and drop the ones that stayed empty.
    optgroups.forEach((group) => {
      if (group.children.length) frag.appendChild(group);
    });

    selectEl.appendChild(frag);
    selectEl.disabled = false;
    this.#syncSelect(selectEl);
    this.#logDebug(`Filled select: ${selectEl.id} with ${options.length} items.`);
  }
}

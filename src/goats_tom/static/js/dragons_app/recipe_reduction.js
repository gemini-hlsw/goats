/**
 * Manages the recipe reduction process including starting, stopping, and updating reduction
 * operations.
 * @param {Object} options - Configuration options for the model.
 * @class
 */
class RecipeReductionModel {
  constructor(options) {
    this.options = options;
    this.api = this.options.api;
    this.recipesUrl = "dragonsrecipes/";
    this.reducesUrl = "dragonsreduce/";
    this._recipeId = null;
    this._currentReduceData = null;
    this.isEditMode = false;
    this.defaultReductionMode = "sq";
    this.defaultDrpkg = "geminidr";
  }

  /**
   * Starts the reduction process for a given set of file IDs associated with a recipe.
   * @param {Array<number>} fileIds - Array of file IDs to be reduced.
   * @returns {Promise<Object>} A promise that resolves to the response from the server.
   * @async
   */
  async startReduce(fileIds) {
    const data = { recipe_id: this.recipeId, file_ids: fileIds };
    try {
      const response = await this.api.post(`${this.reducesUrl}`, data);
      this.currentReduceData = response;
      return response;
    } catch (error) {
      console.error("Error starting reduce:", error);
    }
  }

  /**
   * Stops the reduction process.
   * @param {number} reduceId The ID of the reduction to be stopped.
   * @returns {Promise<Object>} A promise that resolves to the response from the server.
   * @throws {Error} If the API request fails, an error is logged to the console.
   * @async
   */
  async stopReduce() {
    const data = { status: "canceled" };
    if (!this.currentReduceData) return;
    try {
      const response = await this.api.patch(
        `${this.reducesUrl}${this.currentReduceData.id}/`,
        data
      );
      this.reduce = response;
      return response;
    } catch (error) {
      console.error("Error stopping reduce:", error);
    }
  }

  /**
   * Asynchronously fetches help documentation for a specified recipe.
   * @param {string} recipeId The ID of the recipe for which help documentation is being requested.
   * @returns {Promise<Object>} A promise that resolves with the help documentation for the
   * specified recipe.
   * @throws {Error} If the API request fails, an error is logged to the console.
   * @async
   */
  async fetchHelp() {
    try {
      const response = await this.api.get(
        `${this.recipesUrl}${this.recipeId}/?include=help`
      );
      return response;
    } catch (error) {
      console.error("Error fetching recipe help:", error);
    }
  }

  /**
   * Updates the recipe options with the provided parameters.
   * @param {string|null} functionDefinition - The new function definition for the recipe.
   * @param {string|null} uparms - Optional parameters for the recipe.
   * @param {string|null} reductionMode - The reduction mode to be used.
   * @param {string|null} drpkg - The data reduction package to be used.
   * @param {string|null} additionalFiles - Additional files to be included in the reduction.
   * @param {string|null} ucals - Calibration overrides for the reduction.
   * @param {string|null} suffix - Suffix to append to output files.
   * @returns {Promise<Object>} A promise that resolves with the updated recipe options.
   * @throws {Error} If the API request fails, an error is logged to the console.
   * @async
   */
  async updateRecipeOptions(
    functionDefinition = null,
    uparms = null,
    reductionMode = null,
    drpkg = null,
    additionalFiles = null,
    ucals = null,
    suffix = null
  ) {
    // Apply defaults if caller sends null.
    const resolvedReductionMode = reductionMode ?? this.defaultReductionMode;
    const resolvedDrpkg = drpkg ?? this.defaultDrpkg;

    const data = {
      function_definition: functionDefinition,
      uparms,
      reduction_mode: resolvedReductionMode,
      drpkg: resolvedDrpkg,
      additional_files: additionalFiles,
      ucals,
      suffix,
    };

    try {
      const response = await this.api.patch(
        `${this.recipesUrl}${this.recipeId}/`,
        data
      );
      return response;
    } catch (error) {
      console.error("Error updating DRAGONS recipe options:", error);
    }
  }

  get currentReduceData() {
    return this._currentReduceData;
  }

  set currentReduceData(value) {
    this._currentReduceData = value;
  }

  get recipeId() {
    return this._recipeId;
  }

  set recipeId(value) {
    this._recipeId = value;
  }
}

class RecipeReductionTemplate {
  constructor(options) {
    this.options = options;
    this.accordionSetups = {
      buttons: {
        recipeAccordion: "Modify Recipe",
        logAccordion: "Log",
      },
      callbacks: {
        recipeAccordion: this._createRecipeAccordionItem.bind(this),
        logAccordion: this._createLogAccordionItem.bind(this),
      },
      classes: {
        recipeAccordion: [],
        logAccordion: ["p-0", "border", "border-top-0", "rounded-bottom"],
      },
    };
  }

  /**
   * Creates the main container for the files table.
   * @param {Array} data - The data used to create the table.
   * @returns {HTMLElement} The container element.
   */
  create(data) {
    const container = this._createContainer();
    const card = this._createCard(data);

    container.appendChild(card);
    return container;
  }

  /**
   * Creates a container element.
   * @returns {HTMLElement} The container element.
   * @private
   */
  _createContainer() {
    // Don't show anything until a recipe is selected.
    const container = Utils.createElement("div", "d-none");
    return container;
  }

  /**
   * Creates a card container.
   * @return {HTMLElement} The card element.
   */
  _createCard(data) {
    const card = Utils.createElement("div", ["card"]);
    card.append(
      this._createCardHeader(data),
      this._createCardBody(data),
      this._createCardFooter1(data),
      this._createCardFooter2(data)
    );

    return card;
  }

  /**
   * Creates the card body.
   * @returns {HTMLElement} The card body.
   */
  _createCardBody() {
    const cardBody = Utils.createElement("div", "card-body");
    return cardBody;
  }

  /**
   * Creates the card header element with action buttons.
   * @param {Object} data - Data necessary for building the header.
   * @returns {HTMLElement} - A populated card header element.
   * @private
   */
  _createCardHeader(data) {
    const cardHeader = Utils.createElement("div", "card-header");
    const row = Utils.createElement("div", ["row"]);
    const col1 = Utils.createElement("div", ["col", "align-self-center"]);
    const col2 = Utils.createElement("div", ["col", "text-end"]);

    // Create content for column 1.
    const p = Utils.createElement("p", ["my-0", "h5"]);
    p.textContent = `${
      this.options.observationTypeToDisplay[data.observation_type.toLowerCase()]
    } Reduction`;
    col1.appendChild(p);

    // Create content for column 2
    const startButton = Utils.createElement("button", ["btn", "btn-success", "me-1"]);
    const stopButton = Utils.createElement("button", ["btn", "btn-danger"]);
    startButton.dataset.action = "startReduce";
    startButton.textContent = "Start";
    stopButton.textContent = "Stop";
    stopButton.dataset.action = "stopReduce";
    stopButton.disabled = false;
    col2.append(startButton, stopButton);

    // Build the layout.
    row.append(col1, col2);

    cardHeader.appendChild(row);
    return cardHeader;
  }

  /**
   * Creates the first footer for the recipe accordion.
   * @param {Object} data - Data necessary for building the footer.
   * @returns {HTMLElement} - A populated card footer element.
   * @private
   */
  _createCardFooter1(data) {
    // Create footer.
    const cardFooter = Utils.createElement("div", "card-footer");
    const recipeAccordion = this._createAccordion("recipeAccordion", data);
    cardFooter.appendChild(recipeAccordion);
    return cardFooter;
  }

  /**
   * Creates the second footer for the recipe accordion, specifically for logging.
   * @param {Object} data - Data necessary for building the footer.
   * @returns {HTMLElement} - A populated card footer element.
   * @private
   */
  _createCardFooter2(data) {
    const cardFooter = Utils.createElement("div", ["card-footer"]);
    const loggerAccordion = this._createAccordion("logAccordion", data);

    cardFooter.appendChild(loggerAccordion);

    return cardFooter;
  }

  /**
   * Creates an accordion component for recipe modification or logging.
   * @param {string} name - The name identifier for the accordion.
   * @param {Object} data - Data to associate with the accordion.
   * @returns {HTMLElement} - A new accordion element.
   * @private
   */
  _createAccordion(name, data) {
    // Set the ID to reference the recipe ID all the recipe belong to.
    const accordionId = this._createId(data, name);
    const accordion = Utils.createElement("div", ["accordion", "accordion-flush"]);
    accordion.id = accordionId;

    const accordionItem = this._createAccordionItem(name, data);

    accordion.appendChild(accordionItem);

    return accordion;
  }

  /**
   * Creates an accordion item element.
   * @param {string} name - Name identifier for the accordion item.
   * @param {Object} data - Data to associate with the accordion item.
   * @returns {HTMLElement} - A new accordion item element.
   * @private
   */
  _createAccordionItem(name, data) {
    // Create IDs to use to link.
    const collapseId = this._createId(data, `${name}Collapse`);
    const accordionHeaderId = this._createId(data, `${name}AccordionHeader`);

    // Create accordion item.
    const accordionItem = Utils.createElement("div", "accordion-item");

    // Create and configure header.
    const accordionHeader = Utils.createElement("h2", "accordion-header");
    accordionHeader.id = accordionHeaderId;

    // Create and configure accordion button.
    const accordionButton = Utils.createElement("button", ["accordion-button"]);
    accordionButton.setAttribute("type", "button");
    accordionButton.setAttribute("data-toggle", "collapse");
    accordionButton.setAttribute("data-target", `#${collapseId}`);
    accordionButton.setAttribute("aria-expanded", "true");
    accordionButton.setAttribute("aria-controls", collapseId);
    accordionButton.textContent = this.accordionSetups.buttons[name];
    accordionHeader.appendChild(accordionButton);
    accordionItem.appendChild(accordionHeader);

    // Create the collaspible body section that will contain recipe.
    const collapse = Utils.createElement("div", [
      "accordion-collapse",
      "collapse",
      "show",
    ]);
    collapse.id = collapseId;
    collapse.setAttribute("aria-labelledby", accordionHeaderId);

    collapse.setAttribute("data-parent", `#${this._createId(data, name)}`);

    const accordionBody = Utils.createElement("div", [
      "accordion-body",
      ...this.accordionSetups.classes[name],
    ]);

    this.accordionSetups.callbacks[name](accordionBody, data);

    collapse.appendChild(accordionBody);
    accordionItem.appendChild(collapse);

    return accordionItem;
  }

  /**
   * Generates a unique ID for an element based on the data and a suffix.
   * @param {Object} data - Data used to generate the ID base.
   * @param {string} suffix - Suffix to append to the ID.
   * @returns {string} - A unique element ID.
   * @private
   */
  _createId(data, suffix) {
    return `recipe${data.id}${suffix}`;
  }

  /**
   * Initializes and returns an editor element.
   * @param {Object} data - Data associated with the editor.
   * @returns {HTMLElement} - An editor element.
   * @private
   */
  _createEditor(data) {
    // Create code viewer.
    const div = Utils.createElement("div", "mb-1");
    div.id = this._createId(data, "Editor");

    return div;
  }

  /**
   * Generates a set of editor buttons for actions such as edit, save, and reset.
   * @returns {HTMLElement} - A div containing configured buttons.
   * @private
   */
  _createEditorButtons() {
    const row = Utils.createElement("div", "row");
    const col1 = Utils.createElement("div", "col");
    const col2 = Utils.createElement("div", ["col", "text-end"]);

    const editOrSaveButton = Utils.createElement("button", [
      "btn",
      "btn-primary",
      "me-1",
    ]);
    editOrSaveButton.textContent = "Edit";
    editOrSaveButton.dataset.action = "editOrSaveRecipe";

    const resetButton = Utils.createElement("button", ["btn", "btn-secondary"]);
    resetButton.textContent = "Reset";
    resetButton.dataset.action = "resetRecipe";

    const helpButton = Utils.createElement("button", ["btn", "btn-link"]);
    helpButton.textContent = "Help";
    helpButton.dataset.action = "helpRecipe";
    helpButton.setAttribute("data-bs-toggle", "offcanvas");
    helpButton.setAttribute("data-bs-target", `#helpOffcanvas`);

    // Build the layout.
    col1.append(editOrSaveButton, resetButton);
    col2.appendChild(helpButton);
    row.append(col1, col2);

    return row;
  }

  /**
   * Appends editor and editor button components to the provided accordion body.
   * @param {HTMLElement} accordionBody The accordion section where the editor and buttons will be appended.
   */
  _createRecipeAccordionItem(accordionBody, data) {
    const advancedOptions = this._createAdvancedOptions(data);
    const editorDiv = this._createEditor(data);
    const editorButtons = this._createEditorButtons();

    accordionBody.append(advancedOptions, editorDiv, editorButtons);
  }

  /**
   * Creates the advanced DRAGONS options section.
   * These map directly to reduce_data() arguments.
   * @param {Object} data - Data associated with the recipe.
   * @returns {HTMLElement}
   * @private
   */
  _createAdvancedOptions(data) {
    const container = Utils.createElement("div", "mb-3");
    const row = Utils.createElement("div", ["row", "g-3", "mb-3"]);

    const filesLabelCol = Utils.createElement("div", ["col-sm-4"]);
    const filesInputCol = Utils.createElement("div", ["col-sm-8"]);

    const filesId = this._createId(data, "AdditionalFiles");
    const filesLabel = Utils.createElement("label", ["col-form-label"]);
    filesLabel.textContent = "Additional Files";
    filesLabel.htmlFor = filesId;

    const filesInfo = this._createInfoPopover(
      `
      <p><strong>Additional Files</strong> are extra FITS files to include in the
      reduction run. These files are simply appended to the input list and do
      <strong>not</strong> change the selected recipe or primitives.</p>

      <p>Provide a Python-style list of paths <strong>relative to the target
      directory</strong>, for example:</p>

      <code>['M81/GN-2021A-DD-102-9/test1.fits', 'M81/.../test2.fits']</code>

      <p>Use comma-separated values inside <code>[...]</code>.</p>
      `,
      "Additional Input Files"
    );

    const filesInput = Utils.createElement("input", ["form-control"]);
    filesInput.id = filesId;
    filesInput.type = "text";
    filesInput.placeholder = "['M81/GN-2021A-DD-102-9/test.fits']";
    filesInput.value = data.additional_files;
    filesInput.disabled = true;

    filesLabelCol.append(filesLabel, filesInfo);
    filesInputCol.append(filesInput);
    //filesRow.append(filesLabelCol, filesInputCol);

    const modeLabelCol = Utils.createElement("div", ["col-sm-4"]);
    const modeInputCol = Utils.createElement("div", ["col-sm-8"]);

    const modeId = this._createId(data, "Mode");
    const modeLabel = Utils.createElement("label", ["col-form-label"]);
    modeLabel.textContent = "Reduction Mode";
    modeLabel.htmlFor = modeId;

    const modeInfo = this._createInfoPopover(
      `
      <p>Select the DRAGONS reduction mode:</p>
      <ul>
        <li><strong>sq</strong> - Science Quality (default)</li>
        <li><strong>qa</strong> - Quality Assessment</li>
        <li><strong>ql</strong> - Quick Look (in development)</li>
      </ul>
      <p>This value becomes <code>Reduce.mode</code>.</p>
      `,
      "Reduction Mode"
    );

    const modeSelect = Utils.createElement("select", ["form-select"]);
    modeSelect.id = modeId;
    const optSq = new Option("sq (science-quality)", "sq", true, true);
    const optQl = new Option("ql (quick-look)", "ql");
    const optQa = new Option("qa (quality-assurance)", "qa");
    optQl.disabled = true;
    optQa.disabled = true;
    modeSelect.append(optSq, optQl, optQa);
    modeSelect.disabled = true;
    modeSelect.value = data.reduction_mode;

    modeLabelCol.append(modeLabel, modeInfo);
    modeInputCol.append(modeSelect);
    //modeRow.append(modeLabelCol, modeInputCol);

    const drpkgRow = Utils.createElement("div", ["row", "g-3", "mb-3"]);
    const drpkgLabelCol = Utils.createElement("div", ["col-sm-4"]);
    const drpkgInputCol = Utils.createElement("div", ["col-sm-8"]);

    const drpkgId = this._createId(data, "Dprkg");
    const drpkgLabel = Utils.createElement("label", ["col-form-label"]);
    drpkgLabel.textContent = "DR Package";
    drpkgLabel.htmlFor = drpkgId;

    const drpkgInfo = this._createInfoPopover(
      `
      <p><strong>drpkg</strong> selects which DRAGONS recipe+primitive library to use.</p>

      <p>The default is <code>geminidr</code>, the Gemini reduction package.</p>

      <p>Advanced users may point to alternate libraries during instrument or
      third-party development.</p>
      `,
      "Data Reduction Package"
    );

    const drpkgSelect = Utils.createElement("select", ["form-select"]);
    drpkgSelect.id = drpkgId;
    drpkgSelect.append(new Option("geminidr", "geminidr", true, true));
    drpkgSelect.disabled = true;
    drpkgSelect.value = data.drpkg;

    drpkgLabelCol.append(drpkgLabel, drpkgInfo);
    drpkgInputCol.append(drpkgSelect);

    const uparmsLabelCol = Utils.createElement("div", ["col-sm-4"]);
    const uparmsInputCol = Utils.createElement("div", ["col-sm-8"]);

    const uparmsId = this._createId(data, "Uparms");
    const uparmsLabel = Utils.createElement("label", ["col-form-label"]);
    uparmsLabel.textContent = "Optional Parameters";
    uparmsLabel.htmlFor = uparmsId;

    const uparmsInfoButton = this._createInfoPopover(
      `
    <p>Use this input field to set parameter values for primitives in the recipe.</p>
    <p>Input should be formatted as follows:</p>
    <ul>
      <li><code>[('primitive1_name:parameter1_name', parameter1_value), ('primitive2_name:parameter2_name', parameter2_value)]</code></li>
      <li>If the primitive name is omitted, e.g., <code>[('parameter_name', parameter_value)]</code>, the parameter value will be applied to all primitives in the recipe that use this parameter.</li>
    </ul>
    <p>While direct modifications to the recipe can be made using the code block below, it is generally recommended to set parameters using this input field for ease and accuracy.</p>
    `,
      "Set Parameter Values"
    );

    const uparmsInput = Utils.createElement("input", ["form-control"]);
    uparmsInput.type = "text";
    uparmsInput.id = uparmsId;
    uparmsInput.placeholder = "[('primitive:parameter', value)]";
    uparmsInput.value = data.uparms;
    uparmsInput.disabled = true;
    this.uparms = uparmsInput;

    uparmsInputCol.append(uparmsInput);
    uparmsLabelCol.append(uparmsLabel, uparmsInfoButton);

    const ucalsLabelCol = Utils.createElement("div", ["col-sm-4"]);
    const ucalsInputCol = Utils.createElement("div", ["col-sm-8"]);

    const ucalsId = this._createId(data, "Ucals");
    const ucalsLabel = Utils.createElement("label", ["col-form-label"]);
    ucalsLabel.textContent = "Calibration Overrides";
    ucalsLabel.htmlFor = ucalsId;

    const ucalsInfo = this._createInfoPopover(
      `
      <p><strong>ucals</strong> manually override DRAGONS' calibration selection.
      This value is passed directly to <code>Reduce.ucals</code>.</p>

      <p>Provide a Python-style dictionary mapping calibration type to a FITS file
      path <strong>relative to the target directory</strong>.</p>

      <p>Example:</p>
      <code>{ 'processed_bias': 'M81/.../master_bias.fits',
              'processed_flat': 'M81/.../master_flat.fits' }</code>

      <p>Leave empty to use the default calibration manager
      behavior.</p>
      `,
      "Calibration Overrides (ucals)"
    );

    const ucalsInput = Utils.createElement("input", ["form-control", "monospace"]);
    ucalsInput.id = ucalsId;
    ucalsInput.type = "text";
    ucalsInput.placeholder = "{ 'processed_flat': 'path/to/file.fits' }";
    ucalsInput.disabled = true;
    ucalsInput.value = data.ucals;

    ucalsLabelCol.append(ucalsLabel, ucalsInfo);
    ucalsInputCol.append(ucalsInput);

    const suffixLabelCol = Utils.createElement("div", ["col-sm-4"]);
    const suffixInputCol = Utils.createElement("div", ["col-sm-8"]);

    const suffixId = this._createId(data, "Suffix");
    const suffixLabel = Utils.createElement("label", ["col-form-label"]);
    suffixLabel.textContent = "Output Suffix";
    suffixLabel.htmlFor = suffixId;

    const suffixInfo = this._createInfoPopover(
      `
    <p>An optional suffix to append to all reduced output files.</p>
    <p>Example:</p>
    <code>_custom</code>
    <p>Leave empty for DRAGONS' default behavior.</p>
    `,
      "Set Output Suffix"
    );

    const suffixInput = Utils.createElement("input", ["form-control"]);
    suffixInput.id = suffixId;
    suffixInput.type = "text";
    suffixInput.placeholder = "_mysuffix";
    suffixInput.disabled = true;
    suffixInput.value = data.suffix;

    suffixLabelCol.append(suffixLabel, suffixInfo);
    suffixInputCol.append(suffixInput);

    row.append(
      filesLabelCol,
      filesInputCol,
      modeLabelCol,
      modeInputCol,
      drpkgLabelCol,
      drpkgInputCol,
      uparmsLabelCol,
      uparmsInputCol,
      ucalsLabelCol,
      ucalsInputCol,
      suffixLabelCol,
      suffixInputCol
    );

    container.append(row);
    return container;
  }

  /**
   * Creates a help popover link with a standard info icon.
   * @param {string} content - HTML content for the popover.
   * @param {string|null} [title=null] - Optional popover title.
   * @returns {HTMLElement} The anchor element with popover initialized.
   * @private
   */
  _createInfoPopover(content, title = null) {
    const info = Utils.createElement("a", ["link-primary", "ms-1"]);
    info.setAttribute("type", "button");
    info.setAttribute("tabindex", "0");
    info.setAttribute("data-bs-trigger", "focus");
    info.setAttribute("data-bs-toggle", "popover");
    info.setAttribute("data-bs-placement", "top");
    info.setAttribute("data-bs-html", "true");
    info.setAttribute("data-bs-custom-class", "custom-tooltip");
    if (title) {
      info.setAttribute("data-bs-title", title);
    }
    info.setAttribute("data-bs-content", content.trim());

    const icon = Utils.createElement("i", ["fa-solid", "fa-circle-info"]);
    info.appendChild(icon);

    new bootstrap.Popover(info);
    return info;
  }

  /**
   * Creates a log section within an accordion item, used for displaying real-time logs or messages
   * related to the recipe reduction process.
   * @param {HTMLElement} accordionBody - The body of the accordion where the log will be displayed.
   * @param {Object} data - Data associated with the specific recipe, potentially including log
   * entries.
   * @private
   */
  _createLogAccordionItem(accordionBody, data) {
    const div = Utils.createElement("div", ["ps-2"]);
    div.id = this._createId(data, "Logger");
    // this.logger = new Logger(div);

    accordionBody.appendChild(div);
  }
}

/**
 * Represents the view layer for managing the recipe reduction interface.
 * Handles the user interface elements and interactions.
 * @param {Object} template - The template used to render the view.
 * @param {Object} options - Configuration options for the view.
 */
class RecipeReductionView {
  constructor(template, options) {
    this.template = template;
    this.options = options;

    this.container = null;
    this.editor = null;
    this.logger = null;
    this.recipe = null;
    this.progress = null;
    this.stopButton = null;
    this.startButton = null;
    this.editOrSaveButton = null;
    this.resetButton = null;
    this.helpButton = null;
    this.isEditMode = false;
    // Advanced options inputs.
    this.uparmsInput = null;
    this.modeSelect = null;
    this.drpkgSelect = null;
    this.filesInput = null;
    this.ucalsInput = null;
    this.suffixInput = null;
  }

  /**
   * Renders changes to the view based on a specified command.
   * @param {string} viewCmd - The command that specifies the action to perform.
   * @param {Object} parameter - Parameters needed for the rendering action.
   */
  render(viewCmd, parameter) {
    switch (viewCmd) {
      case "create":
        this._create(parameter.parentElement, parameter.data);
        break;
      case "show":
        this._show();
        break;
      case "hide":
        this._hide();
        break;
      case "log":
        this._log(parameter.message);
        break;
      case "enableEditRecipe":
        this._enableEditRecipe();
        break;
      case "disableEdit":
        this._disableEdit();
        break;
      case "updateRecipe":
        this._updateRecipe(parameter.data);
        break;
      case "disableSaveRecipe":
        this._disableSaveRecipe();
        break;
      case "update":
        this._update(parameter.data);
        break;
      case "clearLog":
        this._clearLog();
        break;
      case "startReduce":
        this._startReduce(parameter.data);
        break;
      case "stopReduce":
        this._stopReduce(parameter.data);
        break;
    }
  }
  _startReduce(data) {
    this.startButton.disabled = true;
    this.stopButton.disabled = false;
    if (!data) return;
    this._update(data);
  }

  _stopReduce(data) {
    this.startButton.disabled = false;
    // To let multiple cancels if the first fails.
    this.stopButton.disabled = false;
    if (!data) return;
    this._update(data);
  }

  _clearLog() {
    this.logger.clear();
  }

  _update(data) {
    // TODO: Update button state depending on status.
    this.progress.update(data.status);
    if (["canceled", "done", "error"].includes(data.status)) {
      this.startButton.disabled = false;
      this.stopButton.disabled = false;
    } else {
      this.startButton.disabled = true;
      this.stopButton.disabled = false;
    }
  }

  /**
   * Updates the recipe editor with new data.
   * @param {Object} data - Data containing the recipe details.
   * @private
   */
  _updateRecipe(data) {
    this.editor.setValue(data.active_function_definition, -1);
    this.uparmsInput.value = data.uparms;
    this.ucalsInput.value = data.ucals;
    this.suffixInput.value = data.suffix;
    this.drpkgSelect.value = data.drpkg;
    this.modeSelect.value = data.reduction_mode;
    this.filesInput.value = data.additional_files;
  }

  /**
   * Enables editing mode in the recipe editor.
   * @private
   */
  _enableEditRecipe() {
    this.editor.setReadOnly(false);
    this.editOrSaveButton.textContent = "Save";
    this.editor.container.classList.remove("editor-disabled");
    this.uparmsInput.disabled = false;
    this.ucalsInput.disabled = false;
    this.suffixInput.disabled = false;
    this.drpkgSelect.disabled = false;
    this.modeSelect.disabled = false;
    this.filesInput.disabled = false;
  }

  /**
   * Disables editing mode in the recipe editor, locking changes.
   * @private
   */
  _disableSaveRecipe() {
    this.editor.setReadOnly(true);
    this.editOrSaveButton.textContent = "Edit";
    this.editor.container.classList.add("editor-disabled");
    this.uparmsInput.disabled = true;
    this.ucalsInput.disabled = true;
    this.suffixInput.disabled = true;
    this.drpkgSelect.disabled = true;
    this.modeSelect.disabled = true;
    this.filesInput.disabled = true;
  }

  /**
   * Logs a message to the recipe log interface.
   * @param {string} message - The message to log.
   * @private
   */
  _log(message) {
    this.logger.log(message);
  }

  /**
   * Shows the recipe reduction interface.
   * @private
   */
  _show() {
    this.container.classList.remove("d-none");
  }

  /**
   * Hides the recipe reduction interface.
   * @private
   */
  _hide() {
    this.container.classList.add("d-none");
  }

  /**
   * Creates the initial setup for the recipe reduction interface.
   * @param {HTMLElement} parentElement - The parent element to which the view will be attached.
   * @param {Object} data - The data needed to construct the view.
   * @private
   */
  _create(parentElement, data) {
    this.container = this.template.create(data);

    // Append and build rest of things here.
    this.editor = this._createEditor(data);
    this._updateEditorTheme();
    this.logger = new Logger(this.container.querySelector(`#recipe${data.id}Logger`));
    this.progress = new Progress(this.container.querySelector(".card-body"));
    this.stopButton = this.container.querySelector('[data-action="stopReduce"]');
    this.startButton = this.container.querySelector('[data-action="startReduce"]');
    this.editOrSaveButton = this.container.querySelector(
      '[data-action="editOrSaveRecipe"]'
    );
    this.resetButton = this.container.querySelector('[data-action="resetRecipe"]');
    this.helpButton = this.container.querySelector('[data-action="helpRecipe"]');
    this.uparmsInput = this.container.querySelector(`#recipe${data.id}Uparms`);
    this.ucalsInput = this.container.querySelector(`#recipe${data.id}Ucals`);
    this.suffixInput = this.container.querySelector(`#recipe${data.id}Suffix`);
    this.drpkgSelect = this.container.querySelector(`#recipe${data.id}Dprkg`);
    this.modeSelect = this.container.querySelector(`#recipe${data.id}Mode`);
    this.filesInput = this.container.querySelector(`#recipe${data.id}AdditionalFiles`);
    this.parentElement = parentElement;
    this.parentElement.appendChild(this.container);
  }

  /**
   * Initializes and configures the Ace editor within the view.
   * @param {Object} data - The data used to configure the editor.
   * @returns {Object} - The initialized Ace editor instance.
   * @private
   */
  _createEditor(data) {
    const editorDiv = this.container.querySelector(`#recipe${data.id}Editor`);
    const editor = ace.edit(null);

    // Move cursor back to start with -1.
    editor.setValue(data.active_function_definition, -1);
    editor.session.setMode("ace/mode/python");

    editor.container.style.height = "100%";
    editor.container.style.width = "100%";
    editor.container.style.minHeight = "300px";
    editor.container.classList.add("editor-disabled");
    editor.setReadOnly(true);

    editorDiv.appendChild(editor.container);

    return editor;
  }

  /**
   * Updates the theme of the editor based on user settings.
   * @private
   */
  _updateEditorTheme() {
    const storedTheme = localStorage.getItem("theme");
    const theme =
      storedTheme === "dark"
        ? this.options.editor_themes.dark
        : this.options.editor_themes.light;
    this.editor.setTheme(theme);
  }

  /**
   * Binds UI event callbacks to the view elements based on specified events.
   * @param {string} event - The name of the event to bind.
   * @param {Function} handler - The handler function to execute on the event.
   */
  bindCallback(event, handler) {
    switch (event) {
      case "stopReduce":
        Utils.on(this.stopButton, "click", (e) => {
          handler();
        });
        break;
      case "startReduce":
        Utils.on(this.startButton, "click", () => {
          handler();
        });
        break;
      case "editOrSaveRecipe":
        Utils.on(this.editOrSaveButton, "click", () => {
          handler({
            uparms: this.uparmsInput.value,
            functionDefinition: this.editor.getValue(),
            reductionMode: this.modeSelect.value,
            drpkg: this.drpkgSelect.value,
            additionalFiles: this.filesInput.value,
            ucals: this.ucalsInput.value,
            suffix: this.suffixInput.value,
          });
        });
        break;
      case "resetRecipe":
        Utils.on(this.resetButton, "click", () => {
          handler();
        });
        break;
      case "helpRecipe":
        Utils.on(this.helpButton, "click", () => {
          handler();
        });
        break;
    }
  }
}

/**
 * Manages interactions between the model and view in the recipe reduction context.
 * @param {Object} model - The data model for the recipe reduction.
 * @param {Object} view - The view layer for user interaction.
 * @param {Object} options - Configuration options for the controller.
 */
class RecipeReductionController {
  constructor(model, view, options) {
    this.model = model;
    this.view = view;
    this.options = options;
  }

  /**
   * Initializes the view and model for a new recipe reduction.
   * @param {HTMLElement} parentElement - The container where the component should be rendered.
   * @param {Object} data - Data needed to render the component.
   */
  create(parentElement, data) {
    this.model.recipeId = data.id;
    this.model.identifier = new Identifier(
      null, // No run ID.
      data.observation_type,
      data.observation_class,
      data.object_name
    );
    this.view.render("create", { parentElement, data });
    this._bindCallbacks();
  }

  /**
   * Binds event handlers to view events.
   * @private
   */
  _bindCallbacks() {
    this.view.bindCallback("stopReduce", () => this._stopReduce());
    this.view.bindCallback("startReduce", () => this._startReduce());
    this.view.bindCallback("editOrSaveRecipe", (item) =>
      this._editOrSaveRecipe(
        item.uparms,
        item.functionDefinition,
        item.reductionMode,
        item.drpkg,
        item.additionalFiles,
        item.ucals,
        item.suffix
      )
    );
    this.view.bindCallback("resetRecipe", () => this._resetRecipe());
    this.view.bindCallback("helpRecipe", () => this._helpRecipe());
  }

  /**
   * Starts the reduction process via the model.
   * @private
   */
  async _startReduce() {
    this.view.render("clearLog");
    // TODO: Get all files to send from the associated table.
    const tbody = document.querySelector(
      `#${this.model.identifier.idPrefix}FilesTable tbody`
    );
    // Directly retrieve file IDs from checked checkboxes.
    const fileIds = Array.from(
      tbody.querySelectorAll("input[type='checkbox']:checked")
    ).map((input) => input.closest("tr").dataset.fileId);

    const data = await this.model.startReduce(fileIds);
    this.view.render("startReduce", { data });
  }

  async _editOrSaveRecipe(
    uparms,
    functionDefinition,
    reductionMode,
    drpkg,
    additionalFiles,
    ucals,
    suffix
  ) {
    this.model.isEditMode = !this.model.isEditMode;
    if (this.model.isEditMode) {
      this.view.render("enableEditRecipe");
    } else {
      this.view.render("disableSaveRecipe");
      const data = await this.model.updateRecipeOptions(
        functionDefinition,
        uparms,
        reductionMode,
        drpkg,
        additionalFiles,
        ucals,
        suffix
      );
      this.view.render("updateRecipe", { data });
    }
  }

  /**
   * Resets the recipe details to their default state.
   * @private
   */
  async _resetRecipe() {
    const data = await this.model.updateRecipeOptions();
    this.view.render("updateRecipe", { data });
  }

  /**
   * Logs a message related to the recipe reduction process.
   * @param {string} message - The message to log.
   * @private
   */
  log(message) {
    this.view.render("log", { message });
  }

  update(data) {
    // Update the model with new information.
    this.model.currentReduceData = { id: data.reduce_id };
    this.view.render("update", { data });
  }

  /**
   * Fetches and displays help documentation for the current recipe.
   * @private
   */
  async _helpRecipe() {
    // Clear and show loading bar since it is not hidden.
    window.helpOffcanvas.clearTitleAndContent();
    window.helpOffcanvas.isLoading();

    // Pass in the recipe to get the help for it.
    const data = await this.model.fetchHelp();
    window.helpOffcanvas.updateAndShowPrimitivesDocumentation(data);
  }

  /**
   * Stops the reduction process.
   * @private
   */
  async _stopReduce() {
    const data = await this.model.stopReduce();
    this.view.render("stopReduce", { data });
  }

  /**
   * Makes the recipe reduction interface visible.
   */
  show() {
    this.view.render("show");
  }

  /**
   * Hides the recipe reduction interface.
   */
  hide() {
    this.view.render("hide");
  }
}

/**
 * Main class for managing the recipe reduction component, integrating model, view, and controller layers.
 * @param {HTMLElement} parentElement - The parent element to append the component to.
 * @param {string} runId - A unique identifier for the run associated with the recipe reduction.
 * @param {Object} data - Data necessary for initializing the component.
 * @param {Object} [options={}] - Optional configuration options for the recipe reduction.
 */
class RecipeReduction {
  static #defaultOptions = {
    id: "RecipeReduction",
    observationTypeToDisplay: {
      bias: "Bias",
      flat: "Flat",
      dark: "Dark",
      arc: "Arc",
      pinhole: "Pinhole",
      ronchi: "Ronchi",
      fringe: "Fringe",
      bpm: "BPM",
      standard: "Standard",
      object: "Science",
      other: "Error",
    },
    editor_themes: {
      dark: "ace/theme/cloud9_night",
      light: "ace/theme/dawn",
    },
  };

  constructor(parentElement, data, options = {}) {
    this.options = {
      ...RecipeReduction.#defaultOptions,
      ...options,
      api: window.api,
    };
    const model = new RecipeReductionModel(this.options);
    const template = new RecipeReductionTemplate(this.options);
    const view = new RecipeReductionView(template, this.options);
    this.controller = new RecipeReductionController(model, view, this.options);

    this._init(parentElement, data);
  }

  /**
   * Initializes the component by creating its MVC structure and rendering it.
   * @param {HTMLElement} parentElement - The container where the component will be mounted.
   * @param {string} runId - The run identifier for which the component is created.
   * @param {Object} data - Initialization data for the component.
   * @private
   */
  _init(parentElement, data) {
    this._create(parentElement, data);
  }

  /**
   * Creates the MVC components and attaches them to the parent element.
   * @param {HTMLElement} parentElement - The parent element to attach the component to.
   * @param {Object} data - Data needed for the creation.
   * @private
   */
  _create(parentElement, data) {
    this.controller.create(parentElement, data);
  }

  /**
   * Makes the component visible.
   */
  show() {
    this.controller.show();
  }

  /**
   * Hides the component.
   */
  hide() {
    this.controller.hide();
  }

  update(data) {
    this.controller.update(data);
  }

  log(message) {
    this.controller.log(message);
  }
}

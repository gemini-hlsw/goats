/**
 * Class for building HTML elements.
 * @param {Object} options - Configuration options for the template.
 */
class AvailableFilesTemplate {
  constructor(identifier, options) {
    this.identifier = identifier;
    this.options = options;
  }

  /**
   * Creates the container with available files and form elements.
   * @param {Object} data - The data used to populate the form.
   * @returns {HTMLElement} The container element.
   */
  create(data) {
    const container = this._createContainer();
    const p = this._createHeader();
    const form = this._createForm(data.groups);
    const hr = Utils.createElement("hr");

    container.append(p, form, hr);

    return container;
  }

  /**
   * Creates the header element for the available files section.
   * @returns {HTMLElement} The header element.
   * @private
   */
  _createHeader() {
    const p = Utils.createElement("p", ["mt-3", "mb-2"]);
    p.textContent = "Available Files";

    return p;
  }

  /**
   * Creates a primary container element for the UI.
   * @returns {HTMLElement} The newly created container element.
   * @private
   */
  _createContainer() {
    const container = Utils.createElement("div");
    return container;
  }

  /**
   * Creates a form for filtering and grouping files.
   * @param {Array<string>} groups - An array of grouping options available for files.
   * @returns {HTMLElement} The form element containing input fields and grouping options.
   * @private
   */
  _createForm(groups) {
    const form = Utils.createElement("form");
    form.method = "post";

    // Build the elements for the form.
    const fileFilterRow = this._createFilter();
    const fileGroupingsRow = this._createGroupings(groups);
    const strictFileFilterRow = this._createStrictFilterCheckbox();
    const useAllFilesRow = this._createUseAllFilesCheckbox();

    // Build the button.
    const div = Utils.createElement("div", ["d-flex", "justify-content-end"]);
    const button = Utils.createElement("button", ["btn", "btn-primary"]);
    button.textContent = "Apply Groupings And Filter";
    button.setAttribute("type", "submit");
    div.appendChild(button);

    form.append(
      fileGroupingsRow,
      fileFilterRow,
      strictFileFilterRow,
      useAllFilesRow,
      div
    );

    return form;
  }

  /**
   * Creates a filter input row for file filtering based on user-defined criteria.
   * @returns {HTMLElement} A DOM element representing the row for file filtering input.
   * @private
   */
  _createFilter() {
    const row = Utils.createElement("div", ["row", "ms-1", "mb-1"]);
    const col1 = Utils.createElement("div", ["col-sm-3"]);
    const col2 = Utils.createElement("div", ["col-sm-9"]);

    const id = `${this.identifier.idPrefix}filterExpression`;
    // Build the label.
    const label = Utils.createElement("label", ["col-form-label"]);
    label.setAttribute("for", id);
    label.textContent = "Filter";

    // Build the input.
    const input = Utils.createElement("input", ["form-control"]);
    input.id = id;
    input.setAttribute("type", "text");
    input.setAttribute("placeholder", "exposure_time > 10 and airmass == 1");
    input.name = "filter_expression";

    // Create information popover button with an icon for filter expressions.
    const infoButton = Utils.createElement("a", ["link-primary", "ms-1"]);
    infoButton.setAttribute("type", "button");
    infoButton.setAttribute("tabindex", "0");
    infoButton.setAttribute("data-bs-trigger", "focus");
    infoButton.setAttribute("data-bs-toggle", "popover");
    infoButton.setAttribute("data-bs-placement", "top");
    infoButton.setAttribute("data-bs-html", "true");
    infoButton.setAttribute("data-bs-title", "Filtering Files");
    infoButton.setAttribute("data-bs-custom-class", "custom-tooltip");
    infoButton.setAttribute(
      "data-bs-content",
      `
    <p>Filtering helps with the bookkeeping and creating lists of input files to feed to the reduction. Whatever files are displayed after filtering and checked will be used in the reduction process.</p>
    <p>Use the <strong>astrodata descriptors</strong> as filtering keywords with desired values. To see available descriptors, click on the <strong>Header</strong> option under the <strong>View</strong> drop-down menu for any given file.</p>
    <p>Supported Logical Operators (case sensitive):</p>
    <ul>
      <li><code>and</code></li>
      <li><code>or</code></li>
    </ul>
    <p>Supported Operations:</p>
    <ul>
      <li>Equality and inequality: <code>==</code>, <code>!=</code></li>
      <li>Greater than and less than: <code>&gt;</code>, <code>&lt;</code></li>
      <li>Greater than or equal to and less than or equal to: <code>&gt;=</code>, <code>&lt;=</code></li>
    </ul>
    <p>Supported Time/Date Formats:</p>
    <ul>
      <li><code>ut_time</code>:
        <ul>
          <li><code>"%H:%M:%S.%f"</code></li>
          <li><code>"%H:%M:%S"</code></li>
        </ul>
      </li>
      <li><code>local_time</code>:
        <ul>
          <li><code>"%H:%M:%S.%f"</code></li>
          <li><code>"%H:%M:%S"</code></li>
        </ul>
      </li>
      <li><code>ut_date</code>: <code>"%Y-%m-%d"</code></li>
      <li><code>ut_datetime</code>:
        <ul>
          <li><code>"%Y-%m-%d %H:%M:%S"</code></li>
          <li><code>"%Y-%m-%dT%H:%M:%S"</code></li>
          <li><code>"%Y-%m-%d %H:%M:%S.%f"</code></li>
          <li><code>"%Y-%m-%dT%H:%M:%S.%f"</code></li>
        </ul>
      </li>
    </ul>
  `
    );

    // Create icon element.
    const icon = Utils.createElement("i", ["fa-solid", "fa-circle-info"]);
    infoButton.appendChild(icon);

    new bootstrap.Popover(infoButton);

    // Put together.
    col1.append(label, infoButton);
    col2.append(input);
    row.append(col1, col2);

    return row;
  }

  /**
   * Generates a row with a dropdown for grouping files by specified descriptors.
   * Utilizes the TomSelect library to enhance the dropdown functionality.
   * @param {Array<string>} groups - An array of strings representing the grouping options.
   * @returns {HTMLElement} A DOM element representing the row for file groupings.
   * @private
   */
  _createGroupings(groups) {
    const row = Utils.createElement("div", ["row", "mb-3", "ms-1"]);
    const col1 = Utils.createElement("div", ["col-sm-3"]);
    const col2 = Utils.createElement("div", ["col-sm-9"]);

    // Build the ID.
    const id = `${this.identifier.idPrefix}fileGroupings`;
    // tom-select has a different ID.
    const tsId = `${id}-ts-control`;

    // Build the label.
    const label = Utils.createElement("label", ["col-form-label"]);
    label.setAttribute("for", tsId);
    label.textContent = "Create Groupings";

    // Create information popover button with an icon.
    const infoButton = Utils.createElement("a", ["link-primary", "ms-1"]);
    infoButton.setAttribute("type", "button");
    infoButton.setAttribute("tabindex", "0");
    infoButton.setAttribute("data-bs-trigger", "focus");
    infoButton.setAttribute("data-bs-toggle", "popover");
    infoButton.setAttribute("data-bs-placement", "top");
    infoButton.setAttribute("data-bs-html", "true");
    infoButton.setAttribute("data-bs-title", "Group Files by Astrodata Descriptors");
    infoButton.setAttribute(
      "data-bs-content",
      `
    <div>
      <p>Use this dropdown to create groupings based on shared properties like filters and binnings. 
      Start typing in the select box to search for available descriptors.</p>
      <p class="mb-0">Only available groupings based on astrodata descriptors will be listed.</p>
    </div>
      `
    );

    // Create icon element.
    const icon = Utils.createElement("i", ["fa-solid", "fa-circle-info"]);
    infoButton.appendChild(icon);

    new bootstrap.Popover(infoButton);

    // Build the select.
    const select = Utils.createElement("select", []);
    select.id = id;
    select.name = "group_by";
    select.setAttribute("autocomplete", "off");
    select.multiple = true;

    // Create a document fragment to append options.
    const fragment = document.createDocumentFragment();
    groups.forEach((group) => {
      const option = Utils.createElement("option");
      option.value = group;
      option.textContent = group;
      fragment.appendChild(option);
    });
    select.appendChild(fragment);

    // Put together.
    col1.append(label, infoButton);
    col2.append(select);
    row.append(col1, col2);

    new TomSelect(select, {
      create: false,
      sortField: { field: "text", director: "asc" },
      maxOptions: null,
      onItemAdd: function (value, item) {
        // This handles clearing text and refreshing the options.
        this.setTextboxValue("");
        this.refreshOptions(true);
      },
    });

    return row;
  }

  /**
   * Constructs a checkbox that allows users to access all files for the observation ID without any
   * default filtering.
   * @returns {HTMLElement} A DOM element representing the row containing the checkbox.
   * @private
   */
  _createUseAllFilesCheckbox() {
    const row = Utils.createElement("div", ["row", "mb-1", "ms-1"]);
    const col = Utils.createElement("div", ["col-sm-9", "ms-auto"]);
    const div = Utils.createElement("div", ["form-check"]);

    const id = `${this.identifier.idPrefix}useAllFiles`;

    const checkbox = Utils.createElement("input", ["form-check-input"]);
    checkbox.id = id;
    checkbox.setAttribute("type", "checkbox");
    checkbox.name = "use_all_files";
    checkbox.checked = false;

    const label = Utils.createElement("label", ["form-check-label"]);
    label.setAttribute("for", id);
    label.textContent = "Use all files for observation ID";

    // Create information popover button with an icon.
    const infoButton = Utils.createElement("a", ["link-primary", "ms-1"]);
    infoButton.setAttribute("type", "button");
    infoButton.setAttribute("tabindex", "0");
    infoButton.setAttribute("data-bs-trigger", "focus");
    infoButton.setAttribute("data-bs-toggle", "popover");
    infoButton.setAttribute("data-bs-placement", "top");
    infoButton.setAttribute("data-bs-html", "true");
    infoButton.setAttribute("data-bs-custom-class", "custom-tooltip");
    infoButton.setAttribute("data-bs-title", "Access All Files for This Observation");
    infoButton.setAttribute(
      "data-bs-content",
      `
      <div>
        <p>By default, files are grouped by observation type, observation class, and object name. 
        Enabling this option removes those groupings, giving access to all files for this observation.</p>
        <p class="mb-0">Some reduction recipes require files from multiple categories, making this setting essential for certain cases.</p>
      </div>
      `
    );

    // Create icon element.
    const icon = Utils.createElement("i", ["fa-solid", "fa-circle-info"]);
    infoButton.appendChild(icon);

    new bootstrap.Popover(infoButton);

    div.append(checkbox, label, infoButton);
    col.appendChild(div);
    row.appendChild(col);

    return row;
  }

  /**
   * Constructs a checkbox for the user to specify if strict filtering should be applied.
   * @returns {HTMLElement} A DOM element representing the row containing the strict filter
   * checkbox.
   * @private
   */
  _createStrictFilterCheckbox() {
    const row = Utils.createElement("div", ["row", "mb-1", "ms-1"]);
    const col = Utils.createElement("div", ["col-sm-9", "ms-auto"]);
    const div = Utils.createElement("div", ["form-check"]);

    // Build the ID.
    const id = `${this.identifier.idPrefix}strictFileFilter`;

    // Build the checkbox.
    const checkbox = Utils.createElement("input", ["form-check-input"]);
    checkbox.id = id;
    checkbox.setAttribute("type", "checkbox");
    checkbox.name = "filter_strict";
    checkbox.checked = false;

    // Build the label.
    const label = Utils.createElement("label", ["form-check-label"]);
    label.setAttribute("for", id);
    label.textContent = "Use strict filter expression matching";

    // Create information popover button with an icon.
    const infoButton = Utils.createElement("a", ["link-primary", "ms-1"]);
    infoButton.setAttribute("type", "button");
    infoButton.setAttribute("tabindex", "0");
    infoButton.setAttribute("data-bs-toggle", "popover");
    infoButton.setAttribute("data-bs-placement", "top");
    infoButton.setAttribute("data-bs-trigger", "focus");
    infoButton.setAttribute("data-bs-html", "true");
    infoButton.setAttribute("data-bs-title", "Understanding Strict Matching");
    infoButton.setAttribute(
      "data-bs-content",
      `
      <p>By default, matching is lenient to improve usability:</p>
      <ul>
        <li><code>exposure_time</code> and <code>central_wavelength</code> use 'close enough' matching.</li>
        <li><code>filter_name</code>, <code>disperser</code>, and <code>detector_name</code> use 'pretty name' matching.</li>
      </ul>
      <p>For example:</p>
      <ul>
        <li>Header exposure time of 10.001 seconds matches <code>exposure_time==10</code>.</li>
        <li>Filter 'H_G0203' matches <code>filter_name=='H'</code>.</li>
      </ul>
      <p>Activate the strict flag for exact matches when needed.</p>
    `
    );

    // Create icon element.
    const icon = Utils.createElement("i", ["fa-solid", "fa-circle-info"]);
    infoButton.appendChild(icon);

    new bootstrap.Popover(infoButton);

    // Put together.
    div.append(checkbox, label, infoButton);
    col.appendChild(div);
    row.appendChild(col);

    return row;
  }
}

/**
 * Class representing the data model.
 * @param {Identifier} identifer - Instance of indentifying information.
 * @param {Object} options - Configuration options for the model.
 */
class AvailableFilesModel {
  constructor(identifier, options) {
    this.identifier = identifier;
    this.options = options;
    this.api = this.options.api;
    this.url = "dragonsfiles/";
  }

  /**
   * Fetches, groups, and filters files based on user input from the form.
   * @param {FormData} formData - Form data containing filter and grouping parameters.
   * @returns {Promise<Object>} A promise that resolves to an object containing grouped and filtered files.
   */
  async fetchGroupAndFilterFiles(formData) {
    // Fetch individual items from formData.
    const groupBy = formData.getAll("group_by").length
      ? formData.getAll("group_by")
      : ["all"];
    const filterExpression = formData.get("filter_expression") || "";
    const filterStrict = formData.get("filter_strict") === "on";
    const useAllFiles = formData.get("use_all_files") === "on";

    // Construct query parameters.
    const params = [
      `dragons_run=${encodeURIComponent(this.identifier.runId)}`,
      `group_by=${groupBy.map((gb) => encodeURIComponent(gb)).join("&group_by=")}`,
      `filter_strict=${filterStrict}`,
    ];

    // Determine the appropriate filter expression based on user input.
    if (useAllFiles) {
      if (filterExpression) {
        // Use only the user provided filter expression when 'useAllFiles' is true.
        params.push(`filter_expression=${encodeURIComponent(filterExpression)}`);
      }
    } else {
      // Use combined default and user provided filter expressions when 'useAllFiles' is false.
      let combinedFilterExpression = this.identifier.defaultFilterExpression;
      if (filterExpression) {
        combinedFilterExpression += ` and (${filterExpression})`;
      }
      params.push(`filter_expression=${encodeURIComponent(combinedFilterExpression)}`);
    }

    // Construct the complete URL.
    const url = `${this.url}?${params.join("&")}`;
    try {
      const response = await this.api.get(url);
      return response;
    } catch (error) {
      console.error("Error fetching, grouping, and filtering files:", error);
    }
  }
}

/**
 * Class representing the Available Files View.
 * @param {AvailableFilesTemplate} template - The template used to create the view.
 * @param {Object} options - Configuration options for the view.
 */
class AvailableFilesView {
  constructor(template, identifier, options) {
    this.template = template;
    this.identifier = identifier;
    this.options = options;

    // Pointers to important elements and components.
    this.container = null;
    this.form = null;
    this.filesTable = null;
    this.parentElement = null;

    this.render = this.render.bind(this);
    this.bindCallback = this.bindCallback.bind(this);
  }

  /**
   * Creates the view and appends it to the parent element.
   * @param {HTMLElement} parentElement - The parent element.
   * @param {Object} data - The data to populate the view.
   * @private
   */
  _create(parentElement, data) {
    this.container = this.template.create(data);
    this.filesTable = new FilesTable(
      this.container,
      this.template.identifier,
      data.files
    );
    this.form = this.container.querySelector("form");

    this.parentElement = parentElement;
    this.parentElement.appendChild(this.container);
  }

  /**
   * Updates the files table with filtered files.
   * @param {Array<Object>} filteredFiles - An array of file objects that have been filtered.
   */
  _updateFiles(filteredFiles) {
    this.filesTable.update(filteredFiles);
  }

  /**
   * Renders different components based on the command provided.
   * @param {string} viewCmd - A command that determines what action to perform in the view.
   * @param {Object} parameter - Parameters needed for rendering, such as parent element and data.
   */
  render(viewCmd, parameter) {
    switch (viewCmd) {
      case "create":
        this._create(parameter.parentElement, parameter.data);
        break;
      case "updateFiles":
        this._updateFiles(parameter.filteredFiles);
        break;
    }
  }

  /**
   * Binds UI events to handlers based on the event type.
   * @param {string} event - The event name to bind to an action.
   * @param {Function} handler - The function to execute when the event is triggered.
   */
  bindCallback(event, handler) {
    switch (event) {
      case "submitForm":
        Utils.on(this.form, "submit", (e) => {
          e.preventDefault();
          const formData = new FormData(this.form);
          handler({ formData });
        });
        break;
    }
  }
}

/**
 * Class representing the Available Files Controller.
 * @param {AvailableFilesModel} model - The model for the files.
 * @param {AvailableFilesView} view - The view for the files.
 * @param {Object} options - Configuration options for the controller.
 */
class AvailableFilesController {
  constructor(model, view, identifier, options) {
    this.model = model;
    this.view = view;
    this.identifier = identifier;
    this.options = options;
  }

  /**
   * Creates the available files view and model.
   * @param {HTMLElement} parentElement - The parent element to append the view.
   * @param {Object} data - The data to populate the model and view.
   */
  create(parentElement, data) {
    this.view.render("create", { parentElement, data });
    this._bindCallbacks();
  }

  /**
   * Handles form submission for filtering files.
   * @param {FormData} formData - FormData object containing data from the form fields.
   * @returns {Promise<void>} - Returns a promise that resolves when the filtered files are successfully fetched and rendered.
   * @async
   */
  async _submitForm(formData) {
    const filteredFiles = await this.model.fetchGroupAndFilterFiles(formData);
    this.view.render("updateFiles", { filteredFiles });
  }

  _bindCallbacks() {
    this.view.bindCallback("submitForm", (item) => this._submitForm(item.formData));
  }
}

/**
 * Class for the available files.
 * @param {HTMLElement} parentElement - The parent element to append the available files to.
 * @param {Object} data - The data used to initialize the available files.
 * @param {Identifier} identifier - Instance of indentifying information.
 * @param {Object} [options={}] - Optional configuration options for the available files.
 */
class AvailableFiles {
  static #defaultOptions = {
    id: "AvailableFiles",
  };

  constructor(parentElement, data, identifier, options = {}) {
    this.options = { ...AvailableFiles.#defaultOptions, ...options, api: window.api };
    this.identifier = identifier;
    const model = new AvailableFilesModel(this.identifier, this.options);
    const template = new AvailableFilesTemplate(this.identifier, this.options);
    const view = new AvailableFilesView(
      template,
      parentElement,
      this.identifier,
      this.options
    );
    this.controller = new AvailableFilesController(
      model,
      view,
      this.identifier,
      this.options
    );

    this._create(parentElement, data);
  }

  /**
   * Initializes the available files component.
   * @param {HTMLElement} parentElement - The parent element to append the files to.
   * @param {Object} data - The data to initialize the component with.
   * @private
   */
  _create(parentElement, data) {
    this.controller.create(parentElement, data);
  }
}

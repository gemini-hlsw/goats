/**
 * Template class for managing the processed files section in the UI.
 * @param {Object} options - Configuration options for the template.
 */
class ProcessedFilesTemplate {
  constructor(options) {
    this.options = options;
  }

  /**
   * Creates the container including the card.
   * @param {Object} data - The data to populate the UI components.
   * @returns {HTMLElement} The container element with all UI components.
   */
  create(data) {
    const container = this._createContainer();
    const card = this._createCard(data);

    container.appendChild(card);

    return container;
  }

  /**
   * Formats header data into a table with rows of key-value pairs.
   * @param {Object} data The data object containing key-value pairs to display.
   * @returns {HTMLElement} A table element with key-value pairs.
   */
  createHeaderModalTable(data) {
    // Create the table element.
    const table = Utils.createElement("table", ["table", "table-sm"]);

    // Create and append the table body.
    const tbody = Utils.createElement("tbody");
    for (const [key, value] of Object.entries(data)) {
      const row = Utils.createElement("tr");
      const cellKey = Utils.createElement("td");
      cellKey.textContent = key;
      const cellValue = Utils.createElement("td");
      cellValue.textContent = value;
      row.appendChild(cellKey);
      row.appendChild(cellValue);
      tbody.appendChild(row);
    }
    table.append(tbody);

    return table;
  }

  /**
   * Creates a container element.
   * @returns {HTMLElement} The container element.
   * @private
   */
  _createContainer() {
    const container = Utils.createElement("div");
    return container;
  }

  /**
   * Creates a card component that encapsulates the UI elements.
   * @param {Object} data - The data used to populate the card components.
   * @returns {HTMLElement} The card element.
   * @private
   */
  _createCard(data) {
    const card = Utils.createElement("div", ["card"]);
    card.append(this._createCardHeader(), this._createCardBody(data));

    return card;
  }

  /**
   * Creates the header section of the card.
   * @returns {HTMLElement} The card header element
   * @private
   */
  _createCardHeader() {
    const div = Utils.createElement("div", ["card-header", "h5", "mb-0"]);
    div.textContent = "Processed Files";

    return div;
  }

  /**
   * Creates the body section of the card.
   * @param {Object} data - Data used to populate the body of the card.
   * @return {HTMLElement} The card body element.
   * @private
   */
  _createCardBody(data) {
    const cardBody = Utils.createElement("div", ["card-body"]);
    const accordion = Utils.createElement("div", ["accordion", "accordion-flush"]);
    accordion.id = "processedFilesAccordion";
    accordion.appendChild(this._createAccordion(data));
    cardBody.appendChild(accordion);

    return cardBody;
  }

  /**
   * Creates an accordion component within the card for collapsible content.
   * @param {Object} data - Data used to populate the accordion.
   * @returns {HTMLElement} The accordion element.
   * @private
   */
  _createAccordion(data) {
    const accordion = Utils.createElement("div", ["accordion-item"]);
    const accordionId = `accordion${this.options.id}`;
    accordion.id = accordionId;

    const header = Utils.createElement("h6", ["accordion-header"]);
    const headerId = `header${this.options.id}`;
    header.id = headerId;

    const button = Utils.createElement("button");
    const collapseId = `collapse${this.options.id}`;
    button.className = "accordion-button collapsed";
    button.setAttribute("type", "button");
    button.setAttribute("data-bs-toggle", "collapse");
    button.setAttribute("data-bs-target", `#${collapseId}`);
    button.setAttribute("aria-expanded", "false");
    button.setAttribute("aria-controls", collapseId);
    button.textContent = "Manage Files";

    header.appendChild(button);

    const collapseDiv = Utils.createElement("div");
    collapseDiv.id = collapseId;
    collapseDiv.className = "accordion-collapse collapse";
    collapseDiv.setAttribute("aria-labelledby", headerId);
    collapseDiv.setAttribute("data-bs-parent", `#processedFilesAccordion`);

    const accordionBody = Utils.createElement("div", [
      "accordion-body",
      "accordion-body-overflow",
    ]);
    accordionBody.append(
      this._createToolbar(),
      this._createTable(data),
      this._createLoadingDiv()
    );

    collapseDiv.appendChild(accordionBody);
    accordion.append(header, collapseDiv);

    return accordion;
  }

  /**
   * Creates a table for displaying file data.
   * @param {Object} data - Data used to populate the table.
   * @returns {HTMLElement} The table element.
   * @private
   */
  _createTable(data) {
    const table = Utils.createElement("table", [
      "table",
      "table-borderless",
      "table-sm",
      "table-striped",
    ]);
    table.append(this._createTHead(data), this.createTBody(data));

    return table;
  }

  /**
   * Creates a loading indicator element.
   * @return {HTMLElement} The loading div element with a spinner.
   * @private
   */
  _createLoadingDiv() {
    const div = Utils.createElement("div", ["d-none", "text-center"]);
    div.id = `loading${this.options.id}`;
    const spinner = Utils.createElement("div", ["spinner-border", "text-secondary"]);
    const spinnerInner = Utils.createElement("span", ["visually-hidden"]);
    spinnerInner.textContent = "Loading ...";

    spinner.appendChild(spinnerInner);
    div.appendChild(spinner);

    return div;
  }

  /**
   * Creates a toolbar containing action buttons.
   * @return {HTMLElement} The toolbar element containing buttons.
   * @private
   */
  _createToolbar() {
    const div = Utils.createElement("div");
    div.id = `toolbar${this.options.id}`;
    const row = Utils.createElement("div", ["row", "g-3"]);
    const col = Utils.createElement("div", ["col", "text-end"]);

    const refreshButton = Utils.createElement("button", [
      "btn",
      "btn-secondary",
      "btn-sm",
    ]);
    refreshButton.textContent = " Refresh";
    refreshButton.dataset.action = "refresh";

    // Create and prepend the icon.
    const refreshIcon = Utils.createElement("i", ["fa-solid", "fa-arrow-rotate-right"]);
    refreshButton.prepend(refreshIcon);

    col.append(refreshButton);
    row.append(col);
    div.append(row);

    return div;
  }

  /**
   * Creates a table header with specified columns.
   * @param {Object} data - Data used to determine the file count for the header.
   * @returns {HTMLElement} The table header element (thead).
   * @private
   */
  _createTHead(data) {
    const thead = Utils.createElement("thead");
    const tr = Utils.createElement("tr");

    // Creating a cell for name.
    const thName = Utils.createElement("th", ["fw-normal"]);
    thName.setAttribute("scope", "col");
    thName.textContent = `Filename ${Utils.getFileCountLabel(data.length)}`;
    thName.id = `thName${this.options.id}`;

    // Create a cell for last modified.
    const thLastModified = Utils.createElement("th", ["fw-normal"]);
    thLastModified.setAttribute("scope", "col");
    thLastModified.textContent = "Last Modified (UTC)";

    // Create cell for actions.
    const thActions = Utils.createElement("th", ["fw-normal"]);
    thActions.setAttribute("scope", "col");
    thActions.textContent = "";

    // Create another cell.
    const thAdd = Utils.createElement("th", ["text-end", "fw-normal"]);
    thAdd.setAttribute("scope", "col");
    thAdd.textContent = "Add To GOATS Data Products";

    // Create remove cell.
    const thRemove = Utils.createElement("th", ["text-end", "fw-normal"]);
    thRemove.setAttribute("scope", "col");
    thRemove.textContent = "Delete";

    tr.append(thName, thLastModified, thActions, thAdd, thRemove);
    thead.appendChild(tr);

    return thead;
  }

  /**
   * Creates a tbody element populated with data rows.
   * @param {Array} data - The data to populate the tbody with.
   * @return {HTMLElement} The tbody element filled with data rows.
   */
  createTBody(data) {
    const tbody = Utils.createElement("tbody");
    if (data.length === 0) {
      // If no data, show a message row
      const tr = Utils.createElement("tr");
      const td = Utils.createElement("td");
      td.setAttribute("colspan", "4");
      td.textContent = "No files found...";
      tr.appendChild(td);
      tbody.appendChild(tr);
      return tbody;
    }

    // Loop through each item in the data array to create table rows.
    data.forEach((item) => {
      const tr = Utils.createElement("tr");
      tr.dataset.filename = item.name;
      tr.dataset.filepath = item.path;
      tr.dataset.productId = item.product_id;
      tr.dataset.fileUrl = item.url;

      // Create the filename cell with a data attribute.
      const tdFilename = Utils.createElement("td");
      tdFilename.textContent = `${item.path}/${item.name}`;

      // Create last modified.
      const tdLastModified = Utils.createElement("td");
      tdLastModified.textContent = item.last_modified

      // Build the view dropdown.
      const tdViewer = Utils.createElement("td", ["py-0", "mb-0", "text-end"]);
      const viewDropdown = Utils.createElement("div", "dropdown");
      const viewLink = Utils.createElement("a", [
        "btn",
        "btn-link",
        "dropdown-toggle",
        "pt-0",
      ]);
      viewLink.href = "#";
      viewLink.setAttribute("role", "button");
      viewLink.setAttribute("data-toggle", "dropdown");
      viewLink.setAttribute("aria-expanded", "false");
      viewLink.textContent = "View";

      // Build the dropdown menu.
      const ul = Utils.createElement("ul", ["dropdown-menu", "dropdown-menu-right"]);
      const li1 = Utils.createElement("li");
      const li2 = Utils.createElement("li");
      const li3 = Utils.createElement("li");
      const button1 = Utils.createElement("button", ["dropdown-item", "header-button"]);
      button1.setAttribute("type", "button");
      button1.setAttribute("aria-current", "true");
      button1.textContent = "Header";
      button1.dataset.action = "showHeaderModal";
      const divider = Utils.createElement("hr", "dropdown-divider");
      const button2 = Utils.createElement("button", ["dropdown-item", "js9-button"]);
      button2.setAttribute("type", "button");
      button2.setAttribute("aria-current", "true");
      button2.textContent = "JS9";
      button2.dataset.action = "showJs9";

      li1.appendChild(button1);
      li2.appendChild(divider);
      li3.appendChild(button2);
      ul.append(li1, li2, li3);
      viewDropdown.append(viewLink, ul);
      tdViewer.appendChild(viewDropdown);

      // Create the add to data products button cell.
      const tdAdd = Utils.createElement("td", ["text-end"]);

      if (item.is_dataproduct) {
        // If item is a data product, just show a check icon as text.
        const checkIcon = Utils.createElement("i", [
          "fa-solid",
          "fa-circle-check",
          "text-success",
        ]);
        tdAdd.appendChild(checkIcon);
      } else {
        // Otherwise, create a clickable button to add to data products.
        const addButton = Utils.createElement("a", ["link-secondary"]);
        addButton.setAttribute("type", "button");
        addButton.setAttribute("data-action", "add");

        // Create icon element for button.
        const icon = Utils.createElement("i", ["fa-solid", "fa-circle-plus"]);
        addButton.appendChild(icon);

        tdAdd.appendChild(addButton);
      }

      // Build the remove icon.
      const tdRemove = Utils.createElement("td", ["text-end"]);
      const removeButton = Utils.createElement("a", ["link-danger"]);
      removeButton.setAttribute("type", "button");
      removeButton.setAttribute("data-action", "remove");

      // Create icon element for button.
      const icon = Utils.createElement("i", ["fa-solid", "fa-trash-can"]);
      removeButton.appendChild(icon);
      tdRemove.appendChild(removeButton);

      // Append the cells to the row.
      tr.append(tdFilename, tdLastModified, tdViewer, tdAdd, tdRemove);

      // Append the row to the tbody.
      tbody.appendChild(tr);
    });

    return tbody;
  }
}

/**
 * View class for managing the display of processed files in the UI.
 * @param {ProcessedFilesTemplate} template - Template instance used for rendering the UI.
 * @param {Object} options - Configuration options for the view.
 */
class ProcessedFilesView {
  constructor(template, options) {
    this.template = template;
    this.options = options;
    this.modal = this.options.modal;

    this.container = null;
    this.card = null;
    this.body = null;
    this.table = null;
    this.tbody = null;
    this.thead = null;
    this.loadingDiv = null;
    this.toolbar = null;
    this.parentElement = null;

    this.render = this.render.bind(this);
    this.bindCallback = this.bindCallback.bind(this);
  }

  /**
   * Initializes and creates the UI components in the specified parent element.
   * @param {HTMLElement} parentElement - The container in which the UI should be rendered.
   * @param {Object} data - The data to be used for rendering the UI components.
   * @private
   */
  _create(parentElement, data) {
    this.parentElement = parentElement;
    this.container = this.template.create(data);
    this.card = this.container.querySelector(".card");
    this.body = this.card.querySelector(".accordion");
    this.table = this.card.querySelector("table");
    this.tbody = this.card.querySelector("tbody");
    this.thead = this.card.querySelector("thead");
    this.loadingDiv = this.card.querySelector(`#loading${this.options.id}`);
    this.toolbar = this.card.querySelector(`#toolbar${this.options.id}`);

    this.parentElement.appendChild(this.container);
  }

  /**
   * Updates the table with new data.
   * @param {Array} data - The new data to render in the table.
   * @private
   */
  _update(data) {
    const newTbody = this.template.createTBody(data);
    this.table.replaceChild(newTbody, this.tbody);
    this.tbody = newTbody;

    // Update the file count.
    this.thead.querySelector(
      `#thName${this.options.id}`
    ).textContent = `Filename ${Utils.getFileCountLabel(data.length)}`;
  }

  /**
   * Shows the loading animation and hides the data table.
   * @private
   */
  _loading() {
    this.table.classList.add("d-none");
    this.loadingDiv.classList.remove("d-none");
    this._toggleToolbarButtonsDisabled(true);
  }

  /**
   * Hides the loading animation and shows the data table.
   * @private
   */
  _loaded() {
    this.table.classList.remove("d-none");
    this.loadingDiv.classList.add("d-none");
    this._toggleToolbarButtonsDisabled(false);
  }

  /**
   * Toggles the disabled state of all buttons in the toolbar.
   * @param {boolean} disable - True to disable the buttons, false to enable them.
   * @private
   */
  _toggleToolbarButtonsDisabled(disable) {
    const buttons = this.toolbar.querySelectorAll("button");
    buttons.forEach((button) => (button.disabled = disable));
  }

  /**
   * Displays the header modal with the provided file data.
   * @param {Object} data - The data object containing file information and astrodata descriptors.
   */
  _showHeaderModal(data) {
    const header = `Viewing header for ${data.filename}`;
    // Format and apply to body.
    const body = this.template.createHeaderModalTable(data.astrodata_descriptors);
    this.modal.update(header, body);
    this.modal.show();
  }

  /**
   * Renders changes to the view based on a command.
   * @param {string} viewCmd - The command that dictates the rendering action.
   * @param {Object} parameter - Parameters used for rendering.
   */
  render(viewCmd, parameter) {
    switch (viewCmd) {
      case "update":
        this._update(parameter.data);
        break;
      case "loading":
        this._loading();
        break;
      case "loaded":
        this._loaded();
        break;
      case "error":
        console.log("View found error.");
        break;
      case "create":
        this._create(parameter.parentElement, parameter.data);
        break;
      case "showHeaderModal":
        this._showHeaderModal(parameter.data);
        break;
    }
  }

  /**
   * Binds a callback to an event on the table.
   * @param {string} event - The event to bind.
   * @param {Function} handler - The callback function to execute on event trigger.
   */
  bindCallback(event, handler) {
    const selector = `[data-action="${event}"]`;
    switch (event) {
      case "add":
        Utils.delegate(this.table, selector, "click", (e) => {
          // Find the closest table row to the event target.
          const row = e.target.closest("tr");
          if (!row) return;
          handler({
            filename: row.dataset.filename,
            filepath: row.dataset.filepath,
          });
        });
        break;
      case "remove":
        Utils.delegate(this.table, selector, "click", (e) => {
          // Find the closest table row to the event target.
          const row = e.target.closest("tr");
          if (!row) return;
          handler({
            filename: row.dataset.filename,
            filepath: row.dataset.filepath,
            productId: row.dataset.productId,
          });
        });
        break;
      case "refresh":
        Utils.delegate(this.body, selector, "click", () => handler());
        break;
      case "showJs9":
        Utils.delegate(this.table, selector, "click", (e) => {
          const tr = e.target.closest("tr");
          const fileUrl = tr?.dataset.fileUrl;
          handler({ fileUrl });
        });
        break;
      case "showHeaderModal":
        Utils.delegate(this.table, selector, "click", (e) => {
          const tr = e.target.closest("tr");
          const filepath = tr?.dataset.filepath;
          const filename = tr?.dataset.filename;
          const fullPath = `${filepath}/${filename}`;
          handler({ filepath: fullPath });
        });
        break;
    }
  }
}

/**
 * Model class for managing processed file data.
 * @param {Object} options - Configuration options for the model.
 */
class ProcessedFilesModel {
  constructor(options) {
    this.options = options;
    this._runId = null;
    this._data = null;
    this._previousData = null;
    this.api = this.options.api;
    this.processedFilesUrl = "dragonsprocessedfiles/";
    this.processedFilesHeaderUrl = `${this.processedFilesUrl}header/`;
    this.dragonsDataProductsUrl = "dragonsdataproducts/";
  }

  /**
   * Gets the run ID.
   * @return {number} The run ID.
   */
  get runId() {
    return this._runId;
  }

  /**
   * Sets the run ID.
   * @param {number} value - The run ID to set for future API requests.
   */
  set runId(value) {
    this._runId = value;
  }

  /**
   * Fetches files from the processed directory for the set run ID.
   * @async
   * @throws {Error} Throws an error if the network request fails.
   */
  async fetchFiles() {
    try {
      const response = await this.api.get(`${this.processedFilesUrl}${this.runId}/`);
      this.data = response;
    } catch (error) {
      console.error("Error fetching list of processed files:", error);
      throw error;
    }
  }
  /**
   * Fetches the file header.
   * @async
   * @param {string} filepath - The full filepath.
   * @returns {object} The return data.
   * @throws {Error} Throws an error if the network request fails.
   */
  async fetchFileHeader(filepath) {
    try {
      const body = { filepath };
      const response = await this.api.post(`${this.processedFilesHeaderUrl}`, body);
      return response;
    } catch (error) {
      console.error("Error fetching header of processed file:", error);
      throw error;
    }
  }

  /**
   * Adds a new file to the data product repository and fetches the updated file list.
   * @param {string} filename - The name of the file to add.
   * @param {string} filepath - The path of the file to add.
   */
  async addFile(filename, filepath) {
    try {
      const body = {
        filename: filename,
        filepath: filepath,
        data_product_type: "fits_file",
        dragons_run: this.runId,
      };
      await this.api.post(`${this.dragonsDataProductsUrl}`, body);
      // Fetch the files if the creating was successful.
    } catch (error) {
      console.error(`Error adding file:`, error);
      throw error;
    }
    await this.fetchFiles();
  }

  /**
   * Removes a file from the data product repository.
   * @param {string} filename - The name of the file to remove.
   * @param {string} filepath - The path to the file to remove.
   * @param {string} productId - The product ID associated with the file.
   */
  async removeFile(filename, filepath, productId) {
    try {
      const body = {
        filename: filename,
        filepath: filepath,
        product_id: productId,
        action: "remove",
      };
      const response = await this.api.patch(
        `${this.processedFilesUrl}${this.runId}/`,
        body
      );
      this.data = response;
    } catch (error) {
      console.error(`Error removing file:`, error);
      throw error;
    }
  }

  /**
   * Returns the current data stored in the model.
   * @return {Array} The current array of files.
   */
  get data() {
    return this._data;
  }

  /**
   * Sets the current data for the model and updates the previous data state.
   * @param {Array} value - The new data to set.
   */
  set data(value) {
    this._previousData = this._data;
    this._data = value.files;
  }

  /**
   * Checks if the current data differs from the previous data.
   * @return {boolean} True if data has changed, false otherwise.
   */
  dataChanged() {
    return JSON.stringify(this._data) !== JSON.stringify(this._previousData);
  }
}

/**
 * Controller class for managing interactions between the model and view.
 * @param {ProcessedFilesModel} model - The model component of the feature.
 * @param {ProcessedFilesView} view - The view component of the feature.
 * @param {Object} options - Configuration options for the controller.
 */
class ProcessedFilesController {
  constructor(model, view, options) {
    this.model = model;
    this.view = view;
    this.options = options;
  }

  /**
   * Binds callback functions to handle user interactions.
   * @private
   */
  _bindCallbacks() {
    this.view.bindCallback("refresh", () => this.refresh());
    this.view.bindCallback("add", (item) => this.add(item.filename, item.filepath));
    this.view.bindCallback("remove", (item) =>
      this.remove(item.filename, item.filepath, item.productId)
    );
    this.view.bindCallback("showJs9", (item) => this._showJs9(item.fileUrl));
    this.view.bindCallback("showHeaderModal", (item) =>
      this._showHeaderModal(item.filepath)
    );
  }

  /**
   * Handles the display of the file in the JS9 viewer.
   * @param {string} url - The URL of the file to display in JS9.
   * @private
   */
  _showJs9(fileUrl) {
    openJS9Window(fileUrl);
  }

  /**
   * Handles the display of the file header.
   * @param {number} filepath - The filepath to the header to display.
   * @private
   */
  async _showHeaderModal(filepath) {
    const data = await this.model.fetchFileHeader(filepath);
    // Show the modal.
    this.view.render("showHeaderModal", { data });
  }

  /**
   * Updates the model run ID and view with data.
   * @async
   * @param {number} runId - The run ID to get processed files for.
   */
  async update(runId) {
    this.model.runId = runId;
    await this.refresh();
  }

  /**
   * Initiates the file addition process and updates the view if data has changed.
   * @param {string} filename - The name of the file to add.
   * @param {string} filepath - The path of the file to add.
   */
  async add(filename, filepath) {
    await this.model.addFile(filename, filepath);
    if (this.model.dataChanged()) {
      this.view.render("update", { data: this.model.data });
    }
  }

  /**
   * Initiates the file removal process and updates the view if data has changed.
   * @param {string} filename - The name of the file to remove.
   * @param {string} productId - The product ID associated with the file.
   */
  async remove(filename, filepath, productId) {
    await this.model.removeFile(filename, filepath, productId);
    if (this.model.dataChanged()) {
      this.view.render("update", { data: this.model.data });
    }
  }

  /**
   * Fetches the files and refreshes the view. This does not set the model run ID.
   * @async
   */
  async refresh() {
    this.view.render("loading");
    await Utils.ensureMinimumDuration(this.model.fetchFiles(), 500);
    if (this.model.dataChanged()) {
      this.view.render("update", { data: this.model.data });
    }
    this.view.render("loaded");
  }

  /**
   * Initializes the view with a specified run ID and binds callbacks.
   * @param {HTMLElement} parentElement - The parent element where the view will be rendered.
   * @param {number} runId - The run ID to initialize the view with.
   * @async
   */
  async create(parentElement, runId) {
    this.model.runId = runId;
    await Utils.ensureMinimumDuration(this.model.fetchFiles(), 500);
    this.view.render("create", { parentElement, data: this.model.data });
    this.view.render("loaded");

    this._bindCallbacks();
  }
}

/**
 * The main class that orchestrates the initialization and management of the ProcessedFiles
 * application.
 * @param {HTMLElement} parentElement - The parent element where the application will be mounted.
 * @param {number} runId - The run ID used to fetch processed files.
 * @param {Object} options - Configuration options for the application.
 */
class ProcessedFiles {
  static #defaultOptions = {
    id: "ProcessedFiles",
  };

  constructor(parentElement, runId, options = {}) {
    this.options = {
      ...ProcessedFiles.#defaultOptions,
      ...options,
      api: window.api,
      modal: window.modal,
    };
    this.model = new ProcessedFilesModel(this.options);
    const template = new ProcessedFilesTemplate(this.options);
    this.view = new ProcessedFilesView(template, this.options);
    this.controller = new ProcessedFilesController(this.model, this.view, this.options);

    this._create(parentElement, runId);
  }

  /**
   * Initializes the application components.
   * @param {HTMLElement} parentElement - The parent element to append the application.
   * @param {number} runId - The run ID to use for initialization.
   * @private
   */
  _create(parentElement, runId) {
    this.controller.create(parentElement, runId);
  }

  /**
   * Updates the view and model with a new run ID and refreshes the file list.
   * @param {number} runId - The new run ID to set.
   */
  update(runId) {
    this.controller.update(runId);
  }

  /**
   * Refreshes the view of the files in the processed directory.
   */
  refresh() {
    this.controller.refresh();
  }
}

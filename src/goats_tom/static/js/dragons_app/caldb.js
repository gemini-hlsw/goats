/**
 * Class to manage calibration database UI components.
 * @param {Object} options - Configuration options for the model.
 */
class CaldbTemplate {
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
   */
  _createCardHeader() {
    const div = Utils.createElement("div", ["card-header", "h5", "mb-0"]);
    div.textContent = "Calibration Database";

    return div;
  }

  /**
   * Creates the body section of the card.
   * @param {Object} data - The data used to populate the card body.
   * @returns {HTMLElement} The card body element.
   */
  _createCardBody(data) {
    const cardBody = Utils.createElement("div", ["card-body"]);
    const accordion = Utils.createElement("div", ["accordion", "accordion-flush"]);
    accordion.id = "caldbAccordion";
    accordion.appendChild(this._createAccordion(data));
    cardBody.appendChild(accordion);

    return cardBody;
  }

  /**
   * Creates an accordion component for displaying collapsible content.
   * @param {Object} data - The data used to populate the accordion.
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
    collapseDiv.setAttribute("data-bs-parent", `#caldbAccordion`);

    const accordionBody = Utils.createElement("div", [
      "accordion-body",
      "accordion-body-overflow",
    ]);
    accordionBody.append(this._createToolbar(), this._createTable(data));

    collapseDiv.appendChild(accordionBody);
    accordion.append(header, collapseDiv);

    return accordion;
  }

  /**
   * Creates a table for displaying data.
   * @param {Array} data - The data used to populate the table.
   * @returns {HTMLElement} The table element.
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
   * Builds a toolbar with important actions.
   * @returns {HTMLElement} The toolbar.
   */
  _createToolbar() {
    const div = Utils.createElement("div");
    div.id = `toolbar${this.options.id}`;
    const row = Utils.createElement("div", ["row", "g-3"]);
    const colAdd = Utils.createElement("div", ["col"]);

    // Create form to handle file input.
    const form = Utils.createElement("form");
    form.id = `form${this.options.id}`;

    const fileLabel = Utils.createElement("label", ["btn", "btn-secondary", "btn-sm"]);
    fileLabel.textContent = " Add File";
    fileLabel.setAttribute("for", "fileInputCaldb");

    // Create and prepend the icon.
    const fileIcon = Utils.createElement("i", ["fa-solid", "fa-plus"]);
    fileLabel.prepend(fileIcon);

    // Hide file input to use custom text for button.
    const fileInput = Utils.createElement("input");
    fileInput.type = "file";
    fileInput.name = "file";
    fileInput.style.display = "none";
    fileInput.dataset.action = "add";
    fileInput.id = `fileInput${this.options.id}`;

    form.append(fileLabel, fileInput);
    colAdd.appendChild(form);

    const colRefresh = Utils.createElement("div", ["col", "text-end"]);
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

    colRefresh.appendChild(refreshButton);

    row.append(colAdd, colRefresh);
    div.appendChild(row);

    return div;
  }

  /**
   * Creates a thead element.
   * @return {HTMLElement} The newly created thead element.
   */
  _createTHead(data) {
    const thead = Utils.createElement("thead");
    const tr = Utils.createElement("tr");

    // Creating a cell.
    const thName = Utils.createElement("th", ["fw-normal"]);
    thName.setAttribute("scope", "col");
    thName.textContent = `Filename ${Utils.getFileCountLabel(data.length)}`;
    thName.id = `thName${this.options.id}`;

    // Create cell for actions.
    const thActions = Utils.createElement("th", ["fw-normal"]);
    thActions.setAttribute("scope", "col");
    thActions.textContent = "";

    // Create cell for user uploaded.
    const thUserUploaded = Utils.createElement("th", ["fw-normal"]);
    thUserUploaded.setAttribute("scope", "col");

    // Create another cell.
    const thRemove = Utils.createElement("th", ["text-end", "fw-normal"]);
    thRemove.setAttribute("scope", "col");
    thRemove.textContent = "Remove";

    tr.append(thName, thActions, thUserUploaded, thRemove);
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
      td.setAttribute("colspan", "3");
      td.textContent = "No calibration files found...";
      tr.appendChild(td);
      tbody.appendChild(tr);
      return tbody;
    }

    // Loop through each item in the data array to create table rows.
    data.forEach((item) => {
      const tr = Utils.createElement("tr");
      tr.dataset.filename = item.name;
      tr.dataset.filepath = item.path;
      tr.dataset.fileUrl = item.url;

      // Create the filename cell with a data attribute.
      const tdFilename = Utils.createElement("td");
      tdFilename.textContent = `${item.path}/${item.name}`;

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

      // Create user uploaded flag cell.
      const tdUserUploaded = Utils.createElement("td");
      tdUserUploaded.textContent = item.is_user_uploaded ? "User uploaded" : "";

      // Create the delete button cell.
      const tdRemove = Utils.createElement("td", ["text-end"]);

      const removeButton = Utils.createElement("a", ["link-danger"]);
      removeButton.setAttribute("type", "button");
      removeButton.setAttribute("data-filename", item.name);
      removeButton.setAttribute("data-action", "remove");
      // Create icon element for button.
      const icon = Utils.createElement("i", ["fa-solid", "fa-circle-minus"]);
      removeButton.appendChild(icon);

      tdRemove.appendChild(removeButton);

      // Append the cells to the row.
      tr.append(tdFilename, tdViewer, tdUserUploaded, tdRemove);

      // Append the row to the tbody.
      tbody.appendChild(tr);
    });

    return tbody;
  }
}

/**
 * Constructs the view with a specified template and parent element.
 * @param {Object} template - The template object used for rendering components.
 * @param {Object} options - Configuration options for the model.
 */
class CaldbView {
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
    this.parentElement = null;

    this.render = this.render.bind(this);
    this.bindCallback = this.bindCallback.bind(this);
  }

  /**
   * Creates and appends the calibration database card to the parent element.
   * @param {HTMLElement} parentElement - The parent element where the card will be mounted.
   * @param {Object} data - The initial data used to populate the view.
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
        Utils.delegate(this.body, selector, "change", (e) => {
          if (e.target.files.length > 0) {
            handler({ file: e.target.files[0] });
          }
          // Clear the file input after handling to allow the same file to be selected again.
          e.target.value = "";
        });
        break;
      case "remove":
        Utils.delegate(this.table, selector, "click", (e) =>
          handler({ filename: e.target.dataset.filename })
        );
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
 * Manages the data operations for the calibration database.
 * @param {Object} options - Configuration options for the model.
 */
class CaldbModel {
  constructor(options) {
    this.options = options;
    this._runId = null;
    this.api = this.options.api;
    this.caldbUrl = "dragonscaldb/";
    this.processedFilesHeaderUrl = "dragonsprocessedfiles/header/";
  }

  get runId() {
    return this._runId;
  }

  set runId(value) {
    this._runId = value;
  }

  /**
   * Fetches files from the calibration database for the set run ID.
   * @async
   * @throws {Error} Throws an error if the network request fails.
   */
  async fetchFiles() {
    try {
      const response = await this.api.get(`${this.caldbUrl}${this.runId}/`);
      return response.files;
    } catch (error) {
      console.error("Error fetching list of calibration database files:", error);
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
   * Removes a file from the calibration database.
   * @async
   * @param {string} filename - The name of the file to be removed.
   * @throws {Error} Throws an error if the removal operation fails.
   */
  async removeFile(filename) {
    try {
      const body = {
        filename: filename,
        action: "remove",
      };
      const response = await this.api.patch(`${this.caldbUrl}${this.runId}/`, body);
      return response.files;
    } catch (error) {
      console.error(`Error removing file:`, error);
      throw error;
    }
  }

  /**
   * Adds a file to the calibration database.
   * @async
   * @param {File} file - The file object to upload.
   * @returns {Promise<void>} - A promise that resolves when the file has been added successfully.
   */
  async addFile(file) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("action", "add");

    try {
      const body = formData;
      const response = await this.api.patch(
        `${this.caldbUrl}${this.runId}/`,
        body,
        {},
        false
      );
      return response.files;
    } catch (error) {
      console.error(`Error adding file:`, error);
      throw error;
    }
  }
}

/**
 * Initializes a new controller instance.
 * @param {CaldbModel} model - The data model for the application.
 * @param {CaldbView} view - The UI view for the application.
 * @param {Object} options - Additional configuration options.
 */
class CaldbController {
  constructor(model, view, options) {
    this.model = model;
    this.view = view;
    this.options = options;
  }

  /**
   * Binds callback functions to UI events.
   * @private
   */
  _bindCallbacks() {
    this.view.bindCallback("refresh", () => this.refresh());
    this.view.bindCallback("remove", (item) => this.remove(item.filename));
    this.view.bindCallback("add", (item) => this.add(item.file));
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
   * @param {number} runId - The run ID for the calibration database.
   */
  async update(runId) {
    this.model.runId = runId;
    await this.refresh();
  }

  /**
   * Removes an item by its filename.
   * @async
   * @param {string} filename - The filename of the item to remove.
   */
  async remove(filename) {
    const data = await this.model.removeFile(filename);
    this.view.render("update", { data });
  }

  /**
   * Adds a new file to the calibration database.
   * @async
   * @param {File} file - A file object to add to the database.
   */
  async add(file) {
    const data = await this.model.addFile(file);
    this.view.render("update", { data });
  }

  /**
   * Fetches the files and refreshes the view. This does not set the model run ID.
   * @async
   */
  async refresh() {
    const data = await this.model.fetchFiles();
    this.view.render("update", { data });
  }

  async create(parentElement, runId) {
    this.model.runId = runId;
    const data = await this.model.fetchFiles();
    this.view.render("create", { parentElement, data });

    this._bindCallbacks();
  }
}

/**
 * Constructs the calibration database application and initializes all components.
 * @param {number} runId - The initial run ID to load data for.
 * @param {Object} options - Optional configuration options for the application.
 * @param {FetchWrapper} options.api - An instance of an API handling class to facilitate server
 * requests.
 * @param {string} options.id - An optional ID to uniquely identify elements within the application.
 */
class Caldb {
  static #defaultOptions = {
    id: "Caldb",
  };

  constructor(parentElement, runId, options = {}) {
    this.options = {
      ...Caldb.#defaultOptions,
      ...options,
      api: window.api,
      modal: window.modal,
    };
    this.model = new CaldbModel(this.options);
    const template = new CaldbTemplate(this.options);
    this.view = new CaldbView(template, this.options);
    this.controller = new CaldbController(this.model, this.view, this.options);

    this._create(parentElement, runId);
  }

  /**
   * Initializes the calibration database application by creating the UI components and loading the
   * initial data set.
   * @param {HTMLElement} parentElement - The DOM element where the application is mounted.
   * @param {number} runId - The initial run ID to load data for.
   * @private
   */
  _create(parentElement, runId) {
    this.controller.create(parentElement, runId);
  }

  /**
   * Sets the run ID for the model and triggers an update of the application to reflect the new
   * data.
   * This method is typically used when there is a need to switch the current run context
   * dynamically.
   * @param {number} runId - The new run ID to set and load data for.
   */
  update(runId) {
    this.controller.update(runId);
  }

  /**
   * Initiates a refresh of the current view, typically used to reload data from the server and
   * update the UI.
   * This method can be useful after a data modification operation to ensure the UI is in sync with
   * the backend state.
   */
  refresh() {
    this.controller.refresh();
  }
}

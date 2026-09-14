/**
 * Class representing the template for the Files Table.
 * @param {Object} options - Configuration options for the template.
 */
class FilesTableTemplate {
  constructor(identifier, options) {
    this.identifier = identifier;
    this.options = options;
  }

  /**
   * Creates the main container for the files table.
   * @param {Array} data - The data used to create the table.
   * @returns {HTMLElement} The container element.
   */
  create(data) {
    const container = this._createContainer();
    const table = this._createTable(data);

    container.appendChild(table);

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
   * Creates the table element.
   * @param {Array} data - The data used to create the table.
   * @returns {HTMLElement} The table element.
   * @private
   */
  _createTable(data) {
    const table = Utils.createElement("table", [
      "table",
      "table-sm",
      "table-borderless",
      "table-striped",
    ]);
    table.id = `${this.identifier.idPrefix}${this.options.id}`;

    table.append(this._createThead(data), this.createTbody(data.All.files));

    return table;
  }

  /**
   * Creates the table header (thead) element.
   * @param {Array} data - The data used to create the table header.
   * @returns {HTMLElement} The thead element.
   * @private
   */
  _createThead(data) {
    const thead = Utils.createElement("thead");
    const tr = Utils.createElement("tr");

    // Checkbox for selecting/deselecting all rows.
    const checkboxTh = Utils.createElement("th");
    const checkboxDiv = Utils.createElement("div", ["form-check", "mb-0", "h-100"]);
    const checkbox = Utils.createElement("input", ["form-check-input"]);
    checkbox.type = "checkbox";
    checkbox.checked = true;
    checkbox.id = `${this.identifier.idPrefix}selectAll`;
    const checkboxLabel = Utils.createElement("label", [
      "form-check-label",
      "fw-normal",
    ]);
    checkboxLabel.htmlFor = checkbox.id;
    checkboxLabel.textContent = "Select/Deselect All";
    checkboxDiv.append(checkbox, checkboxLabel);
    checkboxTh.appendChild(checkboxDiv);
    tr.append(checkboxTh);

    // Dropdown for file group selection, dynamically populated based on file group keys.
    const selectTh = Utils.createElement("th");
    const select = Utils.createElement("select", ["form-select"]);
    select.id = `${this.identifier.idPrefix}groups`;
    select.setAttribute("autocomplete", "off");

    // Populate select options dynamically from the files data groups.
    Object.keys(data).forEach((groupKey) => {
      const option = Utils.createElement("option");
      option.value = groupKey;
      option.textContent = `${groupKey} (${data[groupKey].count} files)`;
      if (groupKey === "All" || groupKey === "N/A") option.selected = true;
      select.appendChild(option);
    });

    selectTh.appendChild(select);
    tr.append(selectTh);

    // Label for the created column; clicking it sorts the files by date.
    const createdTh = Utils.createElement("th", "fw-normal");
    createdTh.setAttribute("scope", "col");
    const sortButton = Utils.createElement("button", [
      "btn",
      "btn-link",
      "p-0",
      "text-reset",
      "text-decoration-none",
    ]);
    sortButton.type = "button";
    sortButton.dataset.action = "sortByDate";
    sortButton.title = "Sort by Created";
    sortButton.textContent = "Created (UTC) ";
    const sortIcon = Utils.createElement("i", ["fa-solid", "fa-sort", "text-muted"]);
    sortIcon.classList.add("files-table-sort-icon");
    sortButton.appendChild(sortIcon);
    createdTh.appendChild(sortButton);
    tr.append(createdTh);

    thead.appendChild(tr);
    return thead;
  }

  createGroupsSelectOption(groupKey, count) {
    // Determine the correct label for the option.
    const option = new Option(
      `${Utils.truncateText(groupKey)} ${Utils.getFileCountLabel(count)}`,
      groupKey
    );

    return option;
  }

  /**
   * Creates the table body (tbody) element.
   * @param {Array} data - The data used to populate the tbody, directly containing files.
   * @returns {HTMLElement} The tbody element.
   */
  createTbody(data) {
    const tbody = Utils.createElement("tbody");

    if (data.length === 0) {
      // Handle the case where no files are present
      const tr = Utils.createElement("tr");
      const td = Utils.createElement("td", ["text-center"]);
      td.setAttribute("colspan", "3");
      td.textContent = "No files found...";
      tr.appendChild(td);
      tbody.appendChild(tr);
    } else {
      // Iterate over each file and create a row for each
      data.forEach((file) => {
        const tr = this._createFileTr(file);
        tbody.appendChild(tr);
      });
    }

    return tbody;
  }

  /**
   * Creates a table row (tr) element for a file.
   * @param {Object} file - The file data used to create the table row.
   * @returns {HTMLElement} The table row element.
   * @private
   */
  _createFileTr(file) {
    const tr = Utils.createElement("tr", "align-middle");
    tr.dataset.fileId = file.id;
    tr.dataset.fileUrl = file.url;
    tr.dataset.sortDate = file.created ?? "";
    tr.dataset.sortName = file.product_id;

    const tdCheckbox = Utils.createElement("td", ["py-0", "mb-0"]);
    const checkbox = Utils.createElement("input", [
      "form-check-input",
      "file-checkbox",
    ]);
    const label = Utils.createElement("label", "form-check-label");

    // Configure the checkbox
    checkbox.type = "checkbox";
    checkbox.id = `${this.identifier.idPrefix}file${file.id}${this.options.id}`;
    checkbox.checked = true;
    checkbox.dataset.action = "selectFile";

    // Configure the label.
    label.htmlFor = checkbox.id;
    label.textContent = file.product_id;

    const div = Utils.createElement("div", ["form-check", "mb-0", "h-100"]);
    div.appendChild(checkbox);
    div.appendChild(label);
    tdCheckbox.appendChild(div);
    tr.appendChild(tdCheckbox);

    // Show when the file was added to GOATS; the API sorts on this date.
    const tdCreated = Utils.createElement("td", ["py-0", "mb-0"]);
    tdCreated.textContent = Utils.formatUTCDate(file.created);
    tr.appendChild(tdCreated);

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

    tr.appendChild(tdViewer);

    return tr;
  }
}

/**
 * Class representing the data model for the Files Table.
 * @param {Object} options - Configuration options for the model.
 */
class FilesTableModel {
  constructor(options) {
    this.options = options;
    this.api = this.options.api;
    this._data = null;
    this.filesUrl = "dragonsfiles/";
  }

  get data() {
    return this._data;
  }

  set data(value) {
    this._data = value;
  }

  /**
   * Retrieves the data for a specified group ID.
   * @param {string|number} groupId - The ID of the group to retrieve data for.
   * @returns {Object|null} The group data object if found, otherwise null.
   */
  getGroupData(groupId) {
    return this.data[groupId] || null;
  }

  /**
   * Fetches the details of a specific file by its ID.
   * @async
   * @param {string|number} fileId - The ID of the file to fetch.
   * @returns {Promise<Object|null>} A promise resolving to the file data if the request is
   * successful, otherwise null.
   */
  async fetchFile(fileId) {
    try {
      const response = await this.api.get(
        `${this.filesUrl}${fileId}/?include=astrodata_descriptors`
      );
      return response;
    } catch (error) {
      console.error("Error fetching header:", error);
    }
  }
}

/**
 * Class representing the view for the Files Table.
 * @param {FilesTableTemplate} template - The template used to render the view.
 * @param {Object} options - Configuration options for the view.
 */
class FilesTableView {
  constructor(template, options) {
    this.template = template;
    this.options = options;
    this.modal = options.modal;

    this.container = null;
    this.table = null;
    this.tbody = null;
    this.thead = null;
    this.groupSelect = null;
    this.toggleFilesCheckbox = null;
    this.modal = window.modal;

    this.parentElement = null;
    // `null` keeps the order the server sent; "asc"/"desc" sort by date.
    this.sortDirection = null;

    this.render = this.render.bind(this);
    this.bindCallback = this.bindCallback.bind(this);
    this._toggleSort = this._toggleSort.bind(this);
  }

  /**
   * Returns the files in the requested order, leaving the given array untouched.
   * @param {Array} files - The files to order.
   * @returns {Array} The ordered files.
   * @private
   */
  _sorted(data) {
    return Utils.sortByDate(
      data, this.sortDirection, (file) => file.created, (file) => file.product_id
    );
  }

  /**
   * Toggles the date order by moving existing rows, preserving their state.
   * @private
   */
  _toggleSort() {
    this.sortDirection = this.sortDirection === "desc" ? "asc" : "desc";
    Utils.sortTableRowsByDate(this.tbody, this.sortDirection);
    this._updateSortIcon();
  }

  /**
   * Reflects the active direction on the date column's icon.
   * @private
   */
  _updateSortIcon() {
    const icon = this.thead?.querySelector(".files-table-sort-icon");
    Utils.updateDateSortIcon(icon, this.sortDirection);
  }

  /**
   * Updates the view with new data.
   * @param {Array} data - The new data to update the view with.
   * @private
   */
  _update(data) {
    // Update the select.
    while (this.groupsSelect.options.length > 0) {
      this.groupsSelect.remove(0);
    }
    Object.entries(data).forEach(([groupKey, group], index) => {
      const option = this.template.createGroupsSelectOption(groupKey, group.count);
      this.groupsSelect.add(option);

      if (index === 0) {
        // Set the first option as selected by default and render its files.
        this._updateFiles(group.files);
      }
    });
  }

  /**
   * Displays the header modal with the provided file data.
   * @param {Object} data - The data object containing file information and astrodata descriptors.
   */
  _showHeaderModal(data) {
    const header = `Viewing header for ${data.product_id}`;
    // Format and apply to body.
    const body = this.template.createHeaderModalTable(data.astrodata_descriptors);
    this.modal.update(header, body);
    this.modal.show();
  }

  /**
   * Creates the view and appends it to the parent element.
   * @param {Array} data - The data used to create the view.
   * @param {HTMLElement} parentElement - The parent element to append the view to.
   * @private
   */
  _create(data, parentElement) {
    this.container = this.template.create(data);
    this.table = this.container.querySelector("table");
    this.tbody = this.table.querySelector("tbody");
    this.thead = this.table.querySelector("thead");
    this.groupsSelect = this.thead.querySelector("select");
    this.toggleFilesCheckbox = this.thead.querySelector("input[type='checkbox']");
    this.parentElement = parentElement;

    // Append the container to the parent element.
    this.parentElement.appendChild(this.container);

    this.thead
      .querySelector('[data-action="sortByDate"]')
      ?.addEventListener("click", this._toggleSort);
  }

  /**
   * Renders the view based on the given command.
   * @param {string} viewCmd - The command to render (e.g., "create", "update").
   * @param {Object} parameter - Additional parameters to use during rendering.
   */
  render(viewCmd, parameter) {
    switch (viewCmd) {
      case "create":
        this._create(parameter.data, parameter.parentElement);
        break;
      case "update":
        this._update(parameter.data);
        break;
      case "updateFiles":
        this._updateFiles(parameter.data);
        break;
      case "selectAllFiles":
        this._selectAllFiles(parameter.selectAll);
        break;
      case "setSelectAllCheckbox":
        this._setSelectAllCheckbox();
        break;
      case "showHeaderModal":
        this._showHeaderModal(parameter.data);
        break;
    }
  }

  /**
   * Retrieves all file checkboxes from the table body.
   * @returns {NodeList} The list of file checkboxes.
   * @private
   */
  _getFileCheckboxes() {
    return this.tbody.querySelectorAll("input[type='checkbox']");
  }

  /**
   * Updates the state of the "select all" checkbox based on the individual file checkboxes.
   * @private
   */
  _setSelectAllCheckbox() {
    // Determine the overall check state
    const allChecked = Array.from(this._getFileCheckboxes()).every(
      (checkbox) => checkbox.checked
    );
    this.toggleFilesCheckbox.checked = allChecked;
  }

  /**
   * Updates the table body with new files.
   * @param {Array} data - The new files to update the table body with.
   * @private
   */
  _updateFiles(data) {
    const tbody = this.template.createTbody(this._sorted(data));
    this.table.replaceChild(tbody, this.tbody);
    this.tbody = tbody;
    this._updateSortIcon();
  }

  /**
   * Selects or deselects all file checkboxes based on the "select all" checkbox.
   * @param {boolean} selectAll - Whether to select or deselect all checkboxes.
   * @private
   */
  _selectAllFiles(selectAll) {
    this._getFileCheckboxes().forEach((checkbox) => (checkbox.checked = selectAll));
  }

  /**
   * Binds callback functions to UI events.
   * @param {string} event - The event to bind (e.g., "selectAllFiles", "changeGroup").
   * @param {Function} handler - The callback function to execute.
   */
  bindCallback(event, handler) {
    const selector = `[data-action="${event}"]`;
    switch (event) {
      case "selectAllFiles":
        Utils.on(this.toggleFilesCheckbox, "click", (e) => {
          handler({ selectAll: e.target.checked });
        });
        break;
      case "changeGroup":
        Utils.on(this.groupsSelect, "change", (e) => {
          handler({ groupId: e.target.value });
        });
        break;
      case "selectFile":
        Utils.delegate(this.table, selector, "click", () => handler());
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
          const fileId = tr?.dataset.fileId;
          handler({ fileId });
        });
        break;
    }
  }
}

/**
 * Class representing the controller for the Files Table.
 * @param {FilesTableModel} model - The data model for the files table.
 * @param {FilesTableView} view - The view for the files table.
 * @param {Object} options - Configuration options for the controller.
 */
class FilesTableController {
  constructor(model, view, options) {
    this.model = model;
    this.view = view;
    this.options = options;
  }

  /**
   * Updates the files table with new data.
   * @param {Array} data - The new data to update the table with.
   */
  update(data) {
    this.model.data = data;
    this.view.render("update", { data });
  }

  /**
   * Creates the files table and binds the necessary callbacks.
   * @param {Array} data - The data used to create the table.
   * @param {HTMLElement} parentElement - The parent element to append the table to.
   */
  create(data, parentElement) {
    this.model.data = data;
    this.view.render("create", { data, parentElement });
    this._bindCallbacks();
  }

  /**
   * Binds callback functions to UI events.
   * @private
   */
  _bindCallbacks() {
    this.view.bindCallback("selectAllFiles", (item) =>
      this._selectAllFiles(item.selectAll)
    );
    this.view.bindCallback("showJs9", (item) => this._showJs9(item.fileUrl));
    this.view.bindCallback("showHeaderModal", (item) =>
      this._showHeaderModal(item.fileId)
    );
    this.view.bindCallback("selectFile", () => this._selectFile());
    this.view.bindCallback("changeGroup", (item) => this._changeGroup(item.groupId));
  }

  /**
   * Handles the display of the file header.
   * @param {number} fileId - The ID of the file whose header to display.
   * @private
   */
  async _showHeaderModal(fileId) {
    const data = await this.model.fetchFile(fileId);
    // Show the modal.
    this.view.render("showHeaderModal", { data });
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
   * Handles the selection of an individual file and updates the select all checkbox.
   * @private
   */
  _selectFile() {
    this.view.render("setSelectAllCheckbox");
  }

  /**
   * Handles the change of the selected group.
   * @param {number} groupId - The ID of the selected group.
   * @private
   */
  _changeGroup(groupId) {
    const data = this.model.getGroupData(groupId);
    this.view.render("updateFiles", { data: data.files });
    // TODO: Reset the selectAll state
  }

  /**
   * Selects or deselects all files based on the "select all" checkbox.
   * @param {boolean} selectAll - Whether to select or deselect all files.
   * @private
   */
  _selectAllFiles(selectAll) {
    this.view.render("selectAllFiles", { selectAll: selectAll });
  }
}

/**
 * Class representing the Files Table component.
 * @param {HTMLElement} parentElement - The parent element to append the files table to.
 * @param {Array} data - The initial data to populate the files table with.
 * @param {Object} [options={}] - Optional configuration options for the files table.
 */
class FilesTable {
  static #defaultOptions = {
    id: "FilesTable",
  };

  constructor(parentElement, identifier, data = [], options = {}) {
    this.options = {
      ...FilesTable.#defaultOptions,
      ...options,
      api: window.api,
      modal: window.modal,
    };
    this.identifier = identifier;
    this.model = new FilesTableModel(this.options);
    this.template = new FilesTableTemplate(this.identifier, this.options);
    this.view = new FilesTableView(this.template, this.options);
    this.controller = new FilesTableController(this.model, this.view, this.options);

    this._create(data, parentElement);
  }

  /**
   * Creates the files table and renders it.
   * @param {Array} data - The data used to create the table.
   * @param {HTMLElement} parentElement - The parent element to append the table to.
   * @private
   */
  _create(data, parentElement) {
    this.controller.create(data, parentElement);
  }

  /**
   * Updates the files table with new data.
   * @param {Array} data - The new data to update the table with.
   */
  update(data) {
    this.controller.update(data);
  }
}

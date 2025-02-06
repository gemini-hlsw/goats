const KEYS_TO_DISPLAY = [
  "created",
  "version",
  "directory",
  "config_filename",
  "cal_manager_filename",
  "log_filename",
];

/**
 * Manages the creation and manipulation of HTML elements for displaying run information.
 * @class
 */
class RunTableTemplate {
  createContainer() {
    const container = Utils.createElement("div", "table-responsive");
    return container;
  }

  create() {
    const container = this.createContainer();
    container.appendChild(this.createTable());
    return container;
  }
  /**
   * Creates the main table HTML structure.
   * @returns {HTMLTableElement} A table element with a default tbody.
   */
  createTable() {
    const table = Utils.createElement("table", [
      "table",
      "table-borderless",
      "table-sm",
      "small",
    ]);
    table.appendChild(this.createTBodyDefault());
    return table;
  }

  /**
   * Creates a default tbody element for the table when no data is selected.
   * @returns {HTMLTableSectionElement} A tbody element containing a default message.
   */
  createTBodyDefault() {
    const tbody = Utils.createElement("tbody");
    const tr = Utils.createElement("tr");
    const td = Utils.createElement("td");
    td.colSpan = 2;
    td.textContent = "No run selected...";
    tr.appendChild(td);
    tbody.appendChild(tr);
    return tbody;
  }

  /**
   * Creates a tbody element populated with data for the table.
   * @param {Object} data - The data object to populate the table.
   * @returns {HTMLTableSectionElement} A tbody element containing data rows.
   */
  createTBodyData(data) {
    const tbody = Utils.createElement("tbody");

    KEYS_TO_DISPLAY.forEach((key) => {
      if (data.hasOwnProperty(key)) {
        const tr = Utils.createElement("tr");
        const tdKey = Utils.createElement("td");
        tdKey.textContent = Utils.formatDisplayText(key);
        const tdValue = Utils.createElement("td");
        tdValue.textContent = data[key];
        tr.appendChild(tdKey);
        tr.appendChild(tdValue);
        tbody.appendChild(tr);
      }
    });

    // Determine the documentation URL.
    const dragonsDocsUrl = "https://dragons.readthedocs.io/en";
    const docsUrl = data["version"]
      ? `${dragonsDocsUrl}/v${data["version"]}/`
      : dragonsDocsUrl;

    // Create a row for the documentation link.
    const docRow = Utils.createElement("tr");
    const docCell = Utils.createElement("td");
    docCell.setAttribute("colspan", "2");

    const docLink = Utils.createElement("a");
    docLink.href = docsUrl;
    docLink.setAttribute("target", "_blank");
    docLink.textContent = "View DRAGONS Documentation";

    docCell.appendChild(docLink);
    docRow.appendChild(docCell);
    tbody.appendChild(docRow);

    return tbody;
  }
}

/**
 * Stores and manages the run data for the application.
 * @class
 */
class RunTableModel {
  constructor() {}
}

/**
 * Provides the view component for displaying run information, handling DOM interactions.
 * @class
 * @param {RunTableTemplate} template - The template used for rendering the run table.
 * @param {HTMLElement} parentElement - The DOM element that will contain the run table table.
 */
class RunTableView {
  constructor(template, parentElement) {
    this.template = template;
    this.parentElement = parentElement;

    this.container = this._create();
    this.table = this.container.querySelector(".table");
    this.parentElement.appendChild(this.container);

    this.render = this.render.bind(this);
    this.bindCallback = this.bindCallback.bind(this);
  }
  /**
   * Updates the view by replacing the current tbody with a new one based on provided data.
   * @param {Object} data - The data to update the view with.
   */
  update(data) {
    this.table.replaceChild(
      this.template.createTBodyData(data),
      this.table.querySelector("tbody")
    );
  }
  /**
   * Resets the view by replacing the current tbody with the default one.
   */
  reset() {
    this.table.replaceChild(
      this.template.createTBodyDefault(),
      this.table.querySelector("tbody")
    );
  }

  _create() {
    return this.template.create();
  }

  setVisibility(isVisible) {
    this.container.classList.toggle("d-none", !isVisible);
  }

  /**
   * Renders the view based on the command and parameters provided.
   * @param {string} viewCmd - The command that determines the method to execute.
   * @param {*} parameter - The data or parameters passed to the view method.
   */
  render(viewCmd, parameter) {
    switch (viewCmd) {
      case "update":
        this.update(parameter.data);
        break;
      case "reset":
        this.reset();
        break;
      case "show":
        this.setVisibility(true);
        break;
      case "hide":
        this.setVisibility(false);
        break;
    }
  }

  /**
   * Binds callback functions to view events.
   * @param {string} event - The event name.
   * @param {Function} handler - The callback function to bind.
   */
  bindCallback(event, handler) {}
}

/**
 * Controls interactions between the model and view in the RunTable application.
 * @class
 * @param {RunTableModel} model - The model instance for the controller.
 * @param {RunTableView} view - The view instance for the controller.
 */
class RunTableController {
  constructor(model, view) {
    this.model = model;
    this.view = view;
  }

  /**
   * Displays the data by updating the model and then rendering the view.
   * @param {Object} data - The data to display.
   */
  update(data) {
    this.view.render("update", { data });
  }

  /**
   * Resets the data model and view to their initial state.
   */
  reset() {
    this.view.render("reset");
  }

  show() {
    this.view.render("show");
  }

  hide() {
    this.view.render("hide");
  }
}

/**
 * The main class to interface with the run table components.
 * @class
 * @param {HTMLElement} parentElement - The DOM element to which the run table will be attached.
 */
class RunTable {
  constructor(parentElement) {
    this.model = new RunTableModel();
    this.template = new RunTableTemplate();
    this.view = new RunTableView(this.template, parentElement);
    this.controller = new RunTableController(this.model, this.view);
  }

  /**
   * Public method to update the display with new run information.
   * @param {Object} data - The run data to display.
   */
  update(data) {
    this.controller.update(data);
  }

  /**
   * Public method to reset the run table.
   */
  reset() {
    this.controller.reset();
  }

  show() {
    this.controller.show();
  }

  hide() {
    this.controller.hide();
  }
}

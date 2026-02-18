class FinderChartEditor {
  #container;
  #tableBox;
  #table;
  #tbody;
  #finderCharts;
  #idPrefix;
  #addButton;

  constructor(parentElement, { data = [], idPrefix = "finder-charts" } = {}) {
    if (!(parentElement instanceof HTMLElement)) {
      throw new Error("FinderChartEditor expects an HTMLElement as the parent.");
    }
    this.#finderCharts = Array.isArray(data) ? [...data] : [];
    this.#idPrefix = idPrefix;

    this.#container = Utils.createElement("div", [
      "d-flex",
      "flex-column",
      "gap-3", // keep gap unchanged
    ]);
    parentElement.appendChild(this.#container);

    this.#tableBox = Utils.createElement("div", ["table-responsive"]);
    this.#container.appendChild(this.#tableBox);

    this.#addButton = Utils.createElement("button", [
      "btn",
      "btn-outline-primary",
      "align-self-start",
    ]);
    this.#addButton.type = "button";
    this.#addButton.id = `${this.#idPrefix}-add`;
    this.#addButton.innerHTML = `Add <i class="fa-solid fa-plus ms-1"></i>`;

    this.render();
  }

  setData(data) {
    this.#finderCharts = Array.isArray(data) ? [...data] : [];
    this.render();
  }

  render() {
    this.#tableBox.innerHTML = "";
    this.#container.querySelector(".fc-empty-state")?.remove();
    this.#container.querySelector(".fc-separator")?.remove();

    // Always keep Add button at the end
    this.#container.appendChild(this.#addButton);

    if (!this.#finderCharts.length) {
      const emptyMessage = Utils.createElement("div", [
        "text-muted",
        "fc-empty-state",
      ]);
      emptyMessage.textContent = "No finder charts available.";
      this.#container.insertBefore(emptyMessage, this.#addButton);
    } else {
      // Build table only if data exists (no headers in empty case)
      this.#table = this.#buildTable();
      this.#tableBox.appendChild(this.#table);

      for (const item of this.#finderCharts) {
        this.#tbody.appendChild(this.#row(item));
      }
    }

    // Always insert separator before Add button
    const separator = Utils.createElement("hr", ["my-1", "fc-separator"]);
    this.#container.insertBefore(separator, this.#addButton);
  }

  #buildTable() {
    const table = Utils.createElement("table", [
      "table",
      "table-borderless",
      "align-middle",
      "mb-0",
    ]);

    this.#tbody = document.createElement("tbody");
    table.appendChild(this.#tbody);

    return table;
  }

  #row(item) {
    const tr = document.createElement("tr");

    const id = String(item.id ?? "");
    tr.id = `${this.#idPrefix}-row-${id}`;

    const filename = item.filename ?? "-";
    const attachmentType = item.attachment_type ?? "-";
    const description = item.description ?? "-";
    const lastUpdated = this.#formatDate(item.last_updated);

    // Filename
    const tdFilename = document.createElement("td");
    const fileWrapper = Utils.createElement("div", [
      "d-flex",
      "align-items-center",
      "gap-2",
    ]);

    const fileIcon = Utils.createElement("i", [
      "fa-solid",
      "fa-file",
      "text-muted",
    ]);

    const fileNameSpan = Utils.createElement("span", ["fw-semibold"]);
    fileNameSpan.textContent = filename;

    fileWrapper.appendChild(fileIcon);
    fileWrapper.appendChild(fileNameSpan);
    tdFilename.appendChild(fileWrapper);

    // Type
    const tdType = document.createElement("td");
    const badge = Utils.createElement("span", ["badge", "bg-success"]);
    badge.textContent = attachmentType;
    tdType.appendChild(badge);

    // Description
    const tdDescription = document.createElement("td");
    tdDescription.textContent = description;

    // Updated
    const tdUpdated = document.createElement("td");
    tdUpdated.textContent = lastUpdated;

    // Actions
    const tdActions = document.createElement("td");
    tdActions.className = "text-end";

    const actionsWrapper = Utils.createElement("div", [
      "d-inline-flex",
      "gap-2",
    ]);

    const downloadBtn = Utils.createElement("button", [
      "btn",
      "btn-sm",
      "btn-outline-primary",
    ]);
    downloadBtn.type = "button";
    downloadBtn.id = `${this.#idPrefix}-download-${id}`;
    downloadBtn.innerHTML = `<i class="fa-solid fa-download"></i>`;

    const deleteBtn = Utils.createElement("button", [
      "btn",
      "btn-sm",
      "btn-outline-danger",
    ]);
    deleteBtn.type = "button";
    deleteBtn.id = `${this.#idPrefix}-delete-${id}`;
    deleteBtn.innerHTML = `<i class="fa-solid fa-trash"></i>`;

    actionsWrapper.appendChild(downloadBtn);
    actionsWrapper.appendChild(deleteBtn);
    tdActions.appendChild(actionsWrapper);

    tr.appendChild(tdFilename);
    tr.appendChild(tdType);
    tr.appendChild(tdDescription);
    tr.appendChild(tdUpdated);
    tr.appendChild(tdActions);

    return tr;
  }

  #formatDate(value) {
    if (!value) return "-";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    return d.toLocaleString();
  }
}


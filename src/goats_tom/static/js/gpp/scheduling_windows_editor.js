/**
 * Class representing a UI for configuring scheduling windows.
 *
 * Currently this is a dummy UI only: it does not persist or emit data.
 */
class SchedulingWindowsEditor {
  /** @type {HTMLElement} */
  #container;

  /** @type {HTMLElement} */
  #tableBox;

  /** @type {HTMLElement} */
  #list;

  /**
   * Construct a scheduling windows editor UI.
   *
   * @param {HTMLElement} parentElement - The parent element to render into.
   */
  constructor(parentElement, {data = {} } = {}) {
    if (!(parentElement instanceof HTMLElement)) {
      throw new Error("SchedulingWindowsEditor expects an HTMLElement as the parent.");
    }

    this.#container = Utils.createElement("div", ["d-flex", "flex-column"]);
    parentElement.appendChild(this.#container);

    this.#tableBox = Utils.createElement("div", [
      "bg-body",
      "d-flex",
      "flex-column",
      "gap-3",
    ]);
    this.#container.append(this.#tableBox);

    this.#list = Utils.createElement("div", [
      "d-flex",
      "flex-column",
      "gap-2",
    ]);
    this.#tableBox.append(this.#list);

    // Static example rows (dummy content).
    this.#addRow("Include", "2025-Sep-12 @ 02:46 UTC for 2 days");
    this.#addRow("Exclude", "2025-Sep-13 @ 05:00 UTC through 2025-Sep-23 @ 05:00 UTC");

    this.#tableBox.append(this.#separator());
    this.#tableBox.append(this.#buildTypeControls());
    this.#tableBox.append(this.#buildFromAndModeControls());

    const addBtn = Utils.createElement("button", [
      "btn",
      "btn-outline-primary",
      "align-self-start",
      "mt-2",
    ]);
    addBtn.type = "button";
    addBtn.innerHTML = `<i class="fa-solid fa-plus"></i> Add`;

    addBtn.addEventListener("click", () => {
      // Placeholder hook for future behavior (add new scheduling window row)
    });

    this.#tableBox.append(addBtn);
  }

  /**
   * Create and append a static summary row to the list.
   *
   * @private
   * @param {"Include"|"Exclude"} kind - Rule type.
   * @param {string} text - Human-readable summary of the rule.
   */
  #addRow(kind, text) {
  const row = Utils.createElement("div", [
    "input-group",
    "mb-1",
  ]);

  const badge = Utils.createElement("span", [
    "input-group-text",
    kind === "Include" ? "text-bg-success" : "text-bg-danger",
  ]);
  badge.textContent = kind;
  
    const summary = Utils.createElement("span", [
    "form-control",
  ]);
  summary.textContent = text; 

  const removeBtn = Utils.createElement("button", [
    "btn",
    "btn-danger",
  ]);
  removeBtn.type = "button";
  removeBtn.innerHTML = `<i class="fa-solid fa-minus"></i>`;
  removeBtn.title = "Remove";
  removeBtn.addEventListener("click", () => {});

  row.append(badge, summary, removeBtn);
  this.#list.append(row);
}
  /**
   * Create a horizontal separator between summary and controls.
   *
   * @private
   * @returns {HTMLElement}
   */
  #separator() {
    return Utils.createElement("hr", ["my-2"]);
  }

  /**
   * Build the type controls (Include / Exclude).
   *
   * @private
   * @returns {HTMLElement}
   */
  #buildTypeControls() {
    const group = Utils.createElement("div", [
      "d-flex",
      "align-items-center",
      "gap-3",
      "flex-wrap",
    ]);

    group.append(
      this.#radio("type", "Include", true),
      this.#radio("type", "Exclude", false),
    );

    return group;
  }

  /**
   * Build the "from" datetime and mode (Forever / Through / For + repeat) controls.
   * @private
   * @returns {HTMLElement}
   */
  #buildFromAndModeControls() {
    const row = Utils.createElement("div", [
      "d-flex",
      "align-items-start",
      "gap-3",
      "flex-wrap",
    ]);

    // Left side: "from" datetime + UTC badge
    const fromGroup = Utils.createElement("div", [
      "d-flex",
      "align-items-center",
      "gap-2",
      "flex-wrap",
    ]);

    const fromLabel = Utils.createElement("span", ["text-muted"]);
    fromLabel.textContent = "from";

    const fromInput = Utils.createElement("input", [
      "form-control",
      "form-control-sm",
    ]);
    fromInput.type = "datetime-local";
    fromInput.style.maxWidth = "170px";
    fromInput.value = "2025-09-12T02:46";

    const fromUtcBadge = Utils.createElement("span", [
      "badge",
      "text-bg-secondary",
    ]);
    fromUtcBadge.textContent = "UTC";

    fromGroup.append(fromLabel, fromInput, fromUtcBadge);

    // Right side: modes column
    const modeCol = Utils.createElement("div", [
      "d-flex",
      "flex-column",
      "gap-2",
    ]);

    // Forever
    const foreverRow = Utils.createElement("div", [
      "d-flex",
      "align-items-center",
      "gap-2",
    ]);
    foreverRow.append(this.#radio("mode", "Forever", true));
    modeCol.append(foreverRow);

    // Through
    const throughRow = Utils.createElement("div", [
      "d-flex",
      "align-items-center",
      "gap-2",
      "flex-wrap",
    ]);
    throughRow.append(this.#radio("mode", "Through", false));

    const throughInput = Utils.createElement("input", [
      "form-control",
      "form-control-sm",
    ]);
    throughInput.type = "datetime-local";
    throughInput.style.maxWidth = "170px";
    throughInput.value = "2025-09-15T00:00";

    const throughUtcBadge = Utils.createElement("span", [
      "badge",
      "text-bg-secondary",
    ]);
    throughUtcBadge.textContent = "UTC";

    throughRow.append(throughInput, throughUtcBadge);
    modeCol.append(throughRow);

    // For
    const forRow = Utils.createElement("div", [
      "d-flex",
      "align-items-center",
      "gap-2",
      "flex-wrap",
    ]);
    forRow.append(this.#radio("mode", "For", false));

    const forInput = Utils.createElement("input", [
      "form-control",
      "form-control-sm",
    ]);
    forInput.style.maxWidth = "80px";
    forInput.value = "48:00";

    const forSuffix = Utils.createElement("span", ["text-muted"]);
    forSuffix.textContent = "hours";

    forRow.append(forInput, forSuffix);
    modeCol.append(forRow);

    // Repeat block (indented under "For")
    const repeatBlock = Utils.createElement("div", [
      "d-flex",
      "flex-column",
      "gap-1",
    ]);

    const repeatRow = Utils.createElement("div", [
      "d-flex",
      "align-items-center",
      "gap-2",
      "flex-wrap",
      "ms-4",
    ]);

    const repeatCheckbox = Utils.createElement("input");
    repeatCheckbox.type = "checkbox";
    repeatCheckbox.checked = true;

    const repeatLabel = Utils.createElement("span", ["text-muted"]);
    repeatLabel.textContent = "Repeat with a period of";

    const repeatPeriodInput = Utils.createElement("input", [
      "form-control",
      "form-control-sm",
    ]);
    repeatPeriodInput.style.maxWidth = "110px";
    repeatPeriodInput.value = "60:00:00";
    
    const repeatSuffix = Utils.createElement("span", ["text-muted"]);
    repeatSuffix.textContent = "hours";
   
    repeatRow.append(repeatCheckbox, repeatLabel, repeatPeriodInput, repeatSuffix);
    repeatBlock.append(repeatRow);

    // Repeat: Forever
    const repeatForever = Utils.createElement("label", [
      "form-check",
      "d-flex",
      "align-items-center",
      "gap-2",
      "mb-0",
      "ms-5",
    ]);
    const repeatForeverInput = Utils.createElement("input", [
      "form-check-input",
    ]);
    repeatForeverInput.type = "radio";
    repeatForeverInput.name = "repeatMode";
    repeatForeverInput.checked = true;

    const repeatForeverLabel = Utils.createElement("span", [
      "form-check-label",
    ]);
    repeatForeverLabel.textContent = "Forever";

    repeatForever.append(repeatForeverInput, repeatForeverLabel);
    repeatBlock.append(repeatForever);

    // Repeat: Times
    const repeatTimes = Utils.createElement("label", [
      "form-check",
      "d-flex",
      "align-items-center",
      "gap-2",
      "mb-0",
      "ms-5",
    ]);
    const repeatTimesInput = Utils.createElement("input", [
      "form-check-input",
    ]);
    repeatTimesInput.type = "radio";
    repeatTimesInput.name = "repeatMode";

    const timesCountInput = Utils.createElement("input", [
      "form-control",
      "form-control-sm",
    ]);
    timesCountInput.style.maxWidth = "70px";
    timesCountInput.type = "number";
    timesCountInput.value = "3";

    const timesLabel = Utils.createElement("span", ["form-check-label"]);
    timesLabel.textContent = "times";

    repeatTimes.append(repeatTimesInput, timesCountInput, timesLabel);
    repeatBlock.append(repeatTimes);

    modeCol.append(repeatBlock);

    row.append(fromGroup, modeCol);
    return row;
  }

  /**
   * Create a Bootstrap-style radio input with label.
   *
   * @private
   * @param {string} group - Radio group name (shared `name` attribute).
   * @param {string} text - Label text.
   * @param {boolean} checked - Whether the radio should start checked.
   * @returns {HTMLElement}
   */
  #radio(group, text, checked) {
    const wrapper = Utils.createElement("label", [
      "form-check",
      "d-flex",
      "align-items-center",
      "gap-2",
      "mb-0",
    ]);

    const input = Utils.createElement("input", ["form-check-input"]);
    input.type = "radio";
    input.name = group;
    input.checked = checked;

    const label = Utils.createElement("span", ["form-check-label"]);
    label.textContent = text;

    wrapper.append(input, label);
    return wrapper;
  }
}


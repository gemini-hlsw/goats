const WINDOW_KINDS = Object.freeze({
  INCLUDE: "Include",
  EXCLUDE: "Exclude",
});

/**
 * Format a duration in seconds into a human-readable string.
 *
 * Examples:
 *  - 3660  → "1 hour, 1 minute"
 *  - 86400 → "1 day"
 *
 * @param {number|null|undefined} seconds - Duration in seconds.
 * @returns {string} Human-readable duration or empty string if invalid.
 */
function formatDuration(seconds) {
  if (seconds == null || isNaN(seconds)) return "";

  const abs = Math.abs(seconds);

  const days = Math.floor(abs / 86400);
  const hours = Math.floor((abs % 86400) / 3600);
  const minutes = Math.floor((abs % 3600) / 60);
  const secs = Math.floor(abs % 60);

  const parts = [];

  if (days > 0) {
    parts.push(`${days} day${days === 1 ? "" : "s"}`);
  }
  if (hours > 0) {
    parts.push(`${hours} hour${hours === 1 ? "" : "s"}`);
  }
  if (minutes > 0) {
    parts.push(`${minutes} minute${minutes === 1 ? "" : "s"}`);
  }
  if (secs > 0 && parts.length === 0) {
    parts.push(`${secs} second${secs === 1 ? "" : "s"}`);
  }

  return parts.join(", ");
}

/**
 * Editor component for managing a list of scheduling windows.
 *
 * Renders:
 *  - A list of existing windows with Include/Exclude badges.
 *  - Controls to define a new window (type, start time, mode, repeat).
 *  - An "Add" button (currently stub only).
 */
class SchedulingWindowsEditor {
  #container;
  #tableBox;
  #list;
  #timingWindows;

  /**
   * Construct a scheduling windows editor UI.
   *
   * @param {HTMLElement} parentElement - The parent element to render into.
   * @param {{data?: Array<Object>}} [options] - Initial configuration.
   * @param {Array<Object>} [options.data=[]] - Initial list of timing windows.
   * @throws {Error} If parentElement is not an HTMLElement.
   */
  constructor(parentElement, { data = [] } = {}) {
    if (!(parentElement instanceof HTMLElement)) {
      throw new Error(
        "SchedulingWindowsEditor expects an HTMLElement as the parent.",
      );
    }

    this.#timingWindows = Array.isArray(data) ? [...data] : [];

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

    const separator = Utils.createElement("hr", ["my-1"]);
    this.#tableBox.append(separator);

    this.#tableBox.append(this.#buildTypeControls());
    this.#tableBox.append(this.#buildFromAndModeControls());

    const addBtn = Utils.createElement("button", [
      "btn",
      "btn-outline-primary",
      "align-self-start",
    ]);
    addBtn.type = "button";
    addBtn.innerHTML = `<i class="fa-solid fa-plus"></i> Add`;
    addBtn.addEventListener("click", () => {
      // TODO: hook to open modal or create a new window from current controls
    });
    this.#tableBox.append(addBtn);

    this.#renderList();
  }

  /**
   * Re-render the list of existing timing windows.
   *
   * @private
   */
  #renderList() {
    this.#list.innerHTML = "";

    if (this.#timingWindows.length > 0) {
      this.#timingWindows.forEach((tw, index) => {
        const message = this.#buildMessage(tw);
        this.#addRow(index, tw.inclusion, message);
      });
    } else {
      this.#addRow(null, null, "No time windows have been defined");
    }
  }

  /**
   * Build the human-readable summary message for a timing window.
   *
   * @private
   * @param {Object} tw - Timing window object.
   * @returns {string} Summary message describing the timing window.
   */
  #buildMessage(tw) {
    const start = tw.startUtc ?? "";
    let message = start.replace(" ", " @ ") + " UTC";

    if (!tw.end) {
      message += " forever";
    } else if (tw.end.atUtc) {
      const endMessage = tw.end.atUtc.replace(" ", " @ ") + " UTC";
      message += ` through ${endMessage}`;
    } else if (tw.end.after && !tw.end.repeat) {
      const endMessage = formatDuration(tw.end.after.seconds);
      message += ` for ${endMessage}`;
    } else if (tw.end.after && tw.end.repeat) {
      const periodText = formatDuration(tw.end.repeat.period.seconds);
      const times = tw.end.repeat.times;

      if (times == null) {
        message += ` repeat forever with a period of ${periodText}`;
      } else if (times === 1) {
        message += ` repeat once after ${periodText}`;
      } else {
        message += ` repeat ${times} times with a period of ${periodText}`;
      }
    }

    return message;
  }

  /**
   * Add a visual row for a timing window or the empty-state message.
   *
   * @private
   * @param {number|null} index - Index of the timing window in the array, or null for the empty state.
   * @param {string|null} kind - Window kind ("Include" / "Exclude"), case-insensitive.
   * @param {string} message - Human-readable summary.
   */
  #addRow(index, kind, message) {
    if (!kind) {
      const messageHTML = Utils.createElement("div", ["text-muted", "ps-1"]);
      messageHTML.textContent = message;
      this.#list.append(messageHTML);
      return;
    }

    const key = (kind || "").toUpperCase();
    const normalizedKind = WINDOW_KINDS[key];

    const row = Utils.createElement("div", ["input-group", "mb-1"]);
    row.dataset.index = index;

    const badge = Utils.createElement("span", [
      "input-group-text",
      normalizedKind === "Include" ? "text-bg-success" : "text-bg-danger",
    ]);
    badge.textContent = normalizedKind;

    const summary = Utils.createElement("span", ["form-control"]);
    summary.textContent = message;

    const removeBtn = Utils.createElement("button", ["btn", "btn-danger"]);
    removeBtn.type = "button";
    removeBtn.innerHTML = `<i class="fa-solid fa-minus"></i>`;
    removeBtn.title = "Remove";
    removeBtn.addEventListener("click", () => {
      const rowIndex = row.dataset.index;
      if (rowIndex != null) {
        const numericIndex = Number(rowIndex);
        this.#removeTimingWindowAt(numericIndex);
      }
    });

    row.append(badge, summary, removeBtn);
    this.#list.append(row);
  }

  /**
   * Append a timing window to the internal list and re-render.
   *
   * @private
   * @param {Object} tw - Timing window definition object.
   */
  #addTimingWindows(tw) {
    this.#timingWindows.push(tw);
    this.#renderList();
  }

  /**
   * Remove a timing window at the given index and re-render.
   *
   * Safely does nothing if the index is out of bounds.
   *
   * @private
   * @param {number} index - Index of the timing window to remove.
   */
  #removeTimingWindowAt(index) {
    if (index < 0 || index >= this.#timingWindows.length) return;

    this.#timingWindows.splice(index, 1);
    this.#renderList();
  }

  /**
   * Create a radio button group option.
   *
   * @private
   * @param {string} group - Name of the radio group.
   * @param {string} text - Label text and value.
   * @param {boolean} checked - Whether the radio should start checked.
   * @returns {HTMLLabelElement} A label containing the radio input and its text.
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
    input.value = text;
    input.checked = checked;

    const label = Utils.createElement("span", ["form-check-label"]);
    label.textContent = text;

    wrapper.append(input, label);
    return wrapper;
  }

  /**
   * Build the Include/Exclude type controls (radio group).
   *
   * @private
   * @returns {HTMLDivElement} A container with type radios.
   */
  #buildTypeControls() {
    const group = Utils.createElement("div", [
      "d-flex",
      "align-items-center",
      "gap-3",
      "px-2",
    ]);

    group.append(
      this.#radio("type", "Include", true),
      this.#radio("type", "Exclude", false),
    );

    return group;
  }

  /**
   * Build the "From" datetime and mode controls block (Forever / Through / For + repeat).
   *
   * Also wires up the dynamic behavior to show/hide sections
   * depending on the selected mode and the "repeat" checkbox.
   *
   * @private
   * @returns {HTMLDivElement} A container with all mode controls.
   */
  #buildFromAndModeControls() {
    const row = Utils.createElement("div", [
      "d-flex",
      "align-items-start",
      "gap-3",
      "flex-wrap",
    ]);

    // Left side: "From" datetime + UTC badge
    const fromGroup = Utils.createElement("div", [
      "d-flex",
      "align-items-center",
      "gap-2",
      "flex-wrap",
      "px-2",
    ]);

    const fromLabel = Utils.createElement("span", ["text-muted"]);
    fromLabel.textContent = "From";

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
    const foreverRadio = this.#radio("mode", "Forever", true);
    foreverRow.append(foreverRadio);
    modeCol.append(foreverRow);

    // Through
    const throughRow = Utils.createElement("div", [
      "d-flex",
      "align-items-center",
      "gap-2",
      "flex-wrap",
    ]);
    const throughRadio = this.#radio("mode", "Through", false);
    throughRow.append(throughRadio);

    const throughInputs = Utils.createElement("div", [
      "d-flex",
      "align-items-center",
      "gap-2",
      "flex-wrap",
    ]);

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

    throughInputs.append(throughInput, throughUtcBadge);
    throughRow.append(throughInputs);
    modeCol.append(throughRow);

    // For
    const forRow = Utils.createElement("div", [
      "d-flex",
      "align-items-center",
      "gap-2",
      "flex-wrap",
    ]);
    const forRadio = this.#radio("mode", "For", false);
    forRow.append(forRadio);

    const forInputs = Utils.createElement("div", [
      "d-flex",
      "align-items-center",
      "gap-2",
      "flex-wrap",
    ]);

    const forInput = Utils.createElement("input", [
      "form-control",
      "form-control-sm",
    ]);
    forInput.style.maxWidth = "60px";
    forInput.value = "48:00";

    const forSuffix = Utils.createElement("span", ["text-muted"]);
    forSuffix.textContent = "hours";

    forInputs.append(forInput, forSuffix);
    forRow.append(forInputs);
    modeCol.append(forRow);

    // Repeat block (only makes sense for "For")
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
    repeatCheckbox.checked = false;

    const repeatLabel = Utils.createElement("span", ["text-muted"]);
    repeatLabel.textContent = "Repeat with a period of";

    const repeatPeriodInput = Utils.createElement("input", [
      "form-control",
      "form-control-sm",
    ]);
    repeatPeriodInput.style.maxWidth = "75px";
    repeatPeriodInput.value = "60:00:00";

    const repeatSuffix = Utils.createElement("span", ["text-muted"]);
    repeatSuffix.textContent = "hours";

    repeatRow.append(
      repeatCheckbox,
      repeatLabel,
      repeatPeriodInput,
      repeatSuffix,
    );
    repeatBlock.append(repeatRow);

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

    const timesCountInput = Utils.createElement("input", ["form-control"]);
    timesCountInput.style.maxWidth = "50px";
    timesCountInput.type = "number";
    timesCountInput.value = "1";
    timesCountInput.min = "1";

    const timesLabel = Utils.createElement("span", ["form-check-label"]);
    timesLabel.textContent = "times";

    repeatTimes.append(repeatTimesInput, timesCountInput, timesLabel);
    repeatBlock.append(repeatTimes);

    modeCol.append(repeatBlock);
    row.append(fromGroup, modeCol);

    const hideThroughInputs = () => throughInputs.classList.add("d-none");
    const showThroughInputs = () => throughInputs.classList.remove("d-none");

    const hideForInputs = () => forInputs.classList.add("d-none");
    const showForInputs = () => forInputs.classList.remove("d-none");

    const hideRepeatBlock = () => repeatBlock.classList.add("d-none");
    const showRepeatBlock = () => repeatBlock.classList.remove("d-none");

    const updateModeVisibility = (modeValue) => {
      const isForever = modeValue === "Forever";
      const isThrough = modeValue === "Through";
      const isFor = modeValue === "For";

      if (isThrough) {
        showThroughInputs();
      } else {
        hideThroughInputs();
      }

      if (isFor) {
        showForInputs();
        showRepeatBlock();
      } else {
        hideForInputs();
        hideRepeatBlock();
      }

      if (isForever) {
        hideThroughInputs();
        hideForInputs();
        hideRepeatBlock();
      }
    };

    const updateRepeatVisibility = (enabled) => {
      repeatForever.classList.toggle("d-none", !enabled);
      repeatTimes.classList.toggle("d-none", !enabled);
    };

    const modeRadios = row.querySelectorAll('input[name="mode"]');
    modeRadios.forEach((radio) => {
      radio.addEventListener("change", (event) => {
        if (event.target.checked) {
          updateModeVisibility(event.target.value);
        }
      });
    });

    updateModeVisibility("Forever");

    repeatCheckbox.addEventListener("change", (event) => {
      updateRepeatVisibility(event.target.checked);
    });
    updateRepeatVisibility(repeatCheckbox.checked);

    return row;
  }
}

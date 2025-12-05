const MODES = Object.freeze({
  FOREVER: "Forever",
  THROUGH: "Through",
  FOR: "For",
});

const REPEAT_MODES = Object.freeze({
  FOREVER: "Forever",
  TIMES: "Times",
});

/**
 * Return current UTC datetime formatted for <input type="datetime-local">.
 *
 * @returns {string} Datetime string in "YYYY-MM-DDTHH:MM"
 */
function getNowForDatetimeLocalUtc() {
  return new Date().toISOString().slice(0, 16);
}

/**
 * Format a duration in seconds into a human-readable string.
 *
 * @param {number|null|undefined} seconds - Duration in seconds.
 * @returns {string} Human-readable duration or empty string if invalid.
 */
function secondsToHumanReadableString(seconds) {
  if (seconds == null || Number.isNaN(Number(seconds))) return "";

  const abs = Math.abs(Number(seconds));

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
 */
class SchedulingWindowsEditor {
  /** @type {HTMLElement} */
  #container;
  /** @type {HTMLElement} */
  #tableBox;
  /** @type {HTMLElement} */
  #list;
  /** @type {Array<Object>} */
  #timingWindows;
  /** @type {string} */
  #idPrefix;

  /**
   * Construct a scheduling windows editor UI.
   *
   * @param {HTMLElement} parentElement - The parent element to render into.
   * @param {{data?: Array<Object>, idPrefix?: string}} [options]
   * @param {Array<Object>} [options.data=[]] - Initial list of timing windows.
   * @param {string} [options.idPrefix="scheduling-windows"] - Prefix for element ids.
   * @throws {Error} If parentElement is not an HTMLElement.
   */
  constructor(
    parentElement,
    { data = [], idPrefix = "scheduling-windows" } = {},
  ) {
    if (!(parentElement instanceof HTMLElement)) {
      throw new Error(
        "SchedulingWindowsEditor expects an HTMLElement as the parent.",
      );
    }

    this.#timingWindows = Array.isArray(data) ? [...data] : [];
    this.#idPrefix = idPrefix;

    this.#container = Utils.createElement("div", ["d-flex", "flex-column"]);
    parentElement.appendChild(this.#container);

    this.#tableBox = Utils.createElement("div", [
      "bg-body",
      "d-flex",
      "flex-column",
      "gap-3",
    ]);
    this.#container.append(this.#tableBox);

    this.#list = Utils.createElement("div", ["d-flex", "flex-column", "gap-2"]);
    this.#tableBox.append(this.#list);

    const separator = Utils.createElement("hr", ["my-1"]);
    this.#tableBox.append(separator);

    this.#tableBox.append(this.#buildTypeControls());
    this.#tableBox.append(this.#buildFromAndModeControls());

    // Wire behavior once controls are in the DOM
    this.#wireModeBehavior();

    const addBtn = Utils.createElement("button", [
      "btn",
      "btn-outline-primary",
      "align-self-start",
    ]);
    addBtn.type = "button";
    addBtn.innerHTML = `<i class="fa-solid fa-plus"></i> Add`;
    addBtn.addEventListener("click", () => {
      // TODO: hook to collect form and add a new timing window
      // const tw = this.#collectTimingWindowFromForm();
      // this.#addTimingWindow(tw);
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
    let message = `${start.replace(" ", " @ ")} UTC`;

    if (!tw.end) {
      message += " forever";
    } else if (tw.end.atUtc) {
      const endMessage = `${tw.end.atUtc.replace(" ", " @ ")} UTC`;
      message += ` through ${endMessage}`;
    } else if (tw.end.after && !tw.end.repeat) {
      const endMessage = secondsToHumanReadableString(tw.end.after.seconds);
      message += ` for ${endMessage}`;
    } else if (tw.end.after && tw.end.repeat) {
      const periodText = secondsToHumanReadableString(
        tw.end.repeat.period.seconds,
      );
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

    const normalizedKind = Utils.capitalizeFirstLetter(kind);

    const row = Utils.createElement("div", ["input-group", "mb-1"]);
    row.dataset.index = index;

    const badge = Utils.createElement("span", [
      "input-group-text",
      normalizedKind === "Include" ? "bg-success-subtle" : "bg-danger-subtle",
    ]);
    badge.textContent = normalizedKind;

    const summary = Utils.createElement("span", [
      "form-control",
      "fw-semibold",
    ]);
    summary.textContent = message;

    const removeBtn = Utils.createElement("button", ["btn", "btn-danger"]);
    removeBtn.type = "button";
    removeBtn.innerHTML = `<i class="fa-solid fa-minus"></i>`;
    removeBtn.title = "Remove";
    removeBtn.addEventListener("click", () => {
      const rowIndex = Number(row.dataset.index);
      this.#removeTimingWindowAt(rowIndex);
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
  #addTimingWindow(tw) {
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
    if (!Number.isInteger(index)) return;
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
   * @returns {HTMLDivElement} A wrapper containing the radio and label.
   */
  #radio(group, text, checked) {
    const wrapper = Utils.createElement("div", ["form-check", "mb-0"]);

    const input = Utils.createElement("input", ["form-check-input"]);
    input.type = "radio";
    input.name = group;
    input.value = text;
    input.checked = checked;
    input.id = `${this.#idPrefix}-${group}-${text}`;

    const label = Utils.createElement("label", ["form-check-label"]);
    label.textContent = text;
    label.setAttribute("for", input.id);

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
    const group = Utils.createElement("div", ["input-group", "gap-3", "px-2"]);
    group.append(
      this.#radio("type", "Include", true),
      this.#radio("type", "Exclude", false),
    );
    return group;
  }

  #buildFromAndModeControls() {
    const row = Utils.createElement("div", [
      "d-flex",
      "flex-wrap",
      "align-items-start",
      "gap-3",
      "px-2",
    ]);

    const fromGroup = this.#buildFromControls();
    const modeGroup = this.#buildModeControls();

    row.append(fromGroup, modeGroup);
    return row;
  }

  /**
   * Build the "From" block: label + datetime-local + UTC badge.
   *
   * @private
   * @returns {HTMLDivElement} fromContainer
   */
  #buildFromControls() {
    const fromContainer = Utils.createElement("div", [
      "input-group",
      "input-group-sm",
      "w-auto",
    ]);

    const inputId = `${this.#idPrefix}-from`;

    const label = Utils.createElement("label", [
      "input-group-text",
      "text-muted",
    ]);
    label.textContent = "From";
    label.setAttribute("for", inputId);

    const fromInput = Utils.createElement("input", [
      "form-control",
      "form-control-sm",
    ]);
    fromInput.type = "datetime-local";
    fromInput.style.maxWidth = "170px";
    fromInput.value = getNowForDatetimeLocalUtc();
    frominput.name = "startUtc";
    frominput.id = inputId;

    const badge = Utils.createElement("span", ["input-group-text"]);
    badge.textContent = "UTC";

    fromContainer.append(label, fromInput, badge);
    return fromContainer;
  }

  /**
   * Build the right-hand side mode controls: Forever / Through / For + Repeat.
   *
   * @private
   * @returns {HTMLDivElement} modeContainer
   */
  #buildModeControls() {
    const modeContainer = Utils.createElement("div", [
      "d-flex",
      "flex-column",
      "gap-3",
    ]);

    modeContainer.append(this.#buildForeverRow());
    modeContainer.append(this.#buildThroughRow());
    modeContainer.append(this.#buildForRow());
    modeContainer.append(this.#buildRepeatBlock());

    return modeContainer;
  }

  /**
   * Build the "Forever" row: radio only.
   *
   * @private
   * @returns {HTMLDivElement}
   */
  #buildForeverRow() {
    const row = Utils.createElement("div", [
      "d-flex",
      "align-items-start",
      "gap-2",
    ]);
    const foreverRadio = this.#radio("mode", MODES.FOREVER, true);
    row.append(foreverRadio);
    return row;
  }

  #buildThroughRow() {
    const row = Utils.createElement("div", [
      "input-group",
      "input-group-sm",
      "w-auto",
    ]);

    const radio = this.#radio("mode", MODES.THROUGH, false);
    row.append(radio);
    radio.classList.add("me-2");

    const inputsWrapper = Utils.createElement("div", [
      "input-group",
      "input-group-sm",
      "w-auto",
    ]);

    const input = Utils.createElement("input", [
      "form-control",
      "form-control-sm",
    ]);
    input.type = "datetime-local";
    input.style.maxWidth = "170px";
    input.name = "endAtUtc";

    const badge = Utils.createElement("span", ["input-group-text"]);
    badge.textContent = "UTC";

    inputsWrapper.append(input, badge);
    row.append(inputsWrapper);

    return row;
  }

  /**
   * Build the "For" row: radio + duration input + suffix.
   *
   * @private
   * @returns {HTMLDivElement}
   */
  #buildForRow() {
    const row = Utils.createElement("div", [
      "input-group",
      "input-group-sm",
      "w-auto",
    ]);

    const radio = this.#radio("mode", MODES.FOR, false);
    row.append(radio);
    radio.classList.add("me-2");

    const inputsWrapper = Utils.createElement("div", [
      "input-group",
      "input-group-sm",
      "w-auto",
    ]);

    const input = Utils.createElement("input", [
      "form-control",
      "form-control-sm",
    ]);
    input.style.maxWidth = "60px";
    input.value = "48:00";
    input.name = "durationHours";

    const suffix = Utils.createElement("span", ["input-group-text"]);
    suffix.textContent = "hours";

    inputsWrapper.append(input, suffix);
    row.append(inputsWrapper);

    return row;
  }

  #buildRepeatBlock() {
    const block = Utils.createElement("div", [
      "d-flex",
      "flex-column",
      "gap-1",
    ]);

    const repeatRow = Utils.createElement("div", [
      "d-flex",
      "align-items-start",
      "gap-1",
      "px-4",
    ]);

    const checkbox = Utils.createElement("input", ["form-check-input"]);
    checkbox.type = "checkbox";
    checkbox.checked = false;
    checkbox.name = "repeatEnabled";
    checkbox.classList.add("me-2");

    const checkboxId = `${this.#idPrefix}-repeat-enabled`;
    checkbox.id = checkboxId;

    const label = Utils.createElement("label", ["form-check-label", "me-2"]);
    label.textContent = "Repeat with a period of";
    label.setAttribute("for", checkboxId);

    const periodGroup = Utils.createElement("div", [
      "input-group",
      "input-group-sm",
      "w-auto",
    ]);

    const periodInput = Utils.createElement("input", [
      "form-control",
      "form-control-sm",
    ]);
    periodInput.style.maxWidth = "75px";
    periodInput.name = "repeatPeriod";
    periodInput.id = `${this.#idPrefix}-repeat-period`;

    const suffix = Utils.createElement("span", ["input-group-text"]);
    suffix.textContent = "hours";

    periodGroup.append(periodInput, suffix);
    repeatRow.append(checkbox, label, periodGroup);
    block.append(repeatRow);

    // Forever repeat
    const foreverRow = Utils.createElement("div", [
      "form-check",
      "mb-0",
      "ms-5",
    ]);
    const foreverInput = Utils.createElement("input", ["form-check-input"]);
    foreverInput.type = "radio";
    foreverInput.name = "repeatMode";
    foreverInput.value = REPEAT_MODES.FOREVER;
    foreverInput.checked = true;
    foreverInput.id = `${this.#idPrefix}-repeat-forever`;

    const foreverLabel = Utils.createElement("label", ["form-check-label"]);
    foreverLabel.textContent = "Forever";
    foreverLabel.setAttribute("for", foreverInput.id);

    foreverRow.append(foreverInput, foreverLabel);
    block.append(foreverRow);

    // Times repeat
    const timesRow = Utils.createElement("div", [
      "d-flex",
      "align-items-start",
      "mb-0",
      "ms-5",
    ]);
    const timesRadio = Utils.createElement("input", [
      "form-check-input",
      "me-2",
    ]);
    timesRadio.type = "radio";
    timesRadio.name = "repeatMode";
    timesRadio.value = REPEAT_MODES.TIMES;
    timesRadio.id = `${this.#idPrefix}-repeat-times`;

    const timesGroup = Utils.createElement("div", [
      "input-group",
      "input-group-sm",
      "w-auto",
    ]);

    const timesCountInput = Utils.createElement("input", [
      "form-control",
      "form-control-sm",
    ]);
    timesCountInput.style.maxWidth = "50px";
    timesCountInput.type = "number";
    timesCountInput.min = "1";
    timesCountInput.name = "repeatTimes";
    timesCountInput.id = `${this.#idPrefix}-repeat-times-count`;

    const timesLabel = Utils.createElement("label", ["input-group-text"]);
    timesLabel.textContent = "times";
    timesLabel.setAttribute("for", timesCountInput.id);

    timesGroup.append(timesCountInput, timesLabel);
    timesRow.append(timesRadio, timesGroup);
    block.append(timesRow);

    return block;
  }

  /**
   * Wire dynamic behavior for mode + repeat controls.
   *
   * @private
   */
  #wireModeBehavior() {
    const modeRadios = this.#container.querySelectorAll('input[name="mode"]');

    const throughInput = this.#container.querySelector(
      'input[name="endAtUtc"]',
    );
    const throughRow = throughInput
      ? throughInput.closest(".input-group")
      : null;

    const forInput = this.#container.querySelector(
      'input[name="durationHours"]',
    );
    const forRow = forInput ? forInput.closest(".input-group") : null;

    const repeatCheckbox = this.#container.querySelector(
      'input[name="repeatEnabled"]',
    );
    const repeatBlock = repeatCheckbox
      ? repeatCheckbox.closest(".d-flex.flex-column") ||
        repeatCheckbox.closest("div")
      : null;

    const repeatPeriodInput = this.#container.querySelector(
      'input[name="repeatPeriod"]',
    );

    const repeatModeRadios =
      this.#container.querySelectorAll('input[name="repeatMode"]') || [];

    const repeatForeverInput = Array.from(repeatModeRadios).find(
      (r) => r.value === REPEAT_MODES.FOREVER,
    );
    const repeatTimesInput = Array.from(repeatModeRadios).find(
      (r) => r.value === REPEAT_MODES.TIMES,
    );

    const repeatForeverLabel = repeatForeverInput
      ? repeatForeverInput.closest("label")
      : null;
    const repeatTimesLabel = repeatTimesInput
      ? repeatTimesInput.closest("label")
      : null;

    const timesCountInput = this.#container.querySelector(
      'input[name="repeatTimes"]',
    );

    const hideEl = (el) => el && el.classList.add("d-none");
    const showEl = (el) => el && el.classList.remove("d-none");

    const updateModeVisibility = (modeValue) => {
      const isForever = modeValue === MODES.FOREVER;
      const isThrough = modeValue === MODES.THROUGH;
      const isFor = modeValue === MODES.FOR;

      if (isThrough) {
        showEl(throughRow);
        if (throughInput && !throughInput.value) {
          throughInput.value = getNowForDatetimeLocalUtc();
        }
      } else {
        hideEl(throughRow);
      }

      if (isFor) {
        showEl(forRow);
        showEl(repeatBlock);
      } else {
        hideEl(forRow);
        hideEl(repeatBlock);
      }

      if (isForever) {
        hideEl(throughRow);
        hideEl(forRow);
        hideEl(repeatBlock);
      }
    };

    const updateTimesInputState = () => {
      if (!repeatCheckbox || !timesCountInput || !repeatTimesInput) return;

      const repeatEnabled = repeatCheckbox.checked;
      const timesSelected = repeatTimesInput.checked;
      const shouldEnableTimes = repeatEnabled && timesSelected;

      timesCountInput.disabled = !shouldEnableTimes;

      if (shouldEnableTimes && !timesCountInput.value) {
        timesCountInput.value = "1";
      } else if (!shouldEnableTimes) {
        timesCountInput.value = "";
      }
    };

    const updateRepeatVisibility = (enabled) => {
      if (repeatForeverLabel) {
        repeatForeverLabel.classList.toggle("d-none", !enabled);
      }
      if (repeatTimesLabel) {
        repeatTimesLabel.classList.toggle("d-none", !enabled);
      }

      if (repeatBlock) {
        const repeatInputs = repeatBlock.querySelectorAll("input");
        repeatInputs.forEach((input) => {
          if (input === repeatCheckbox) return;
          input.disabled = !enabled;
        });
      }

      if (repeatPeriodInput) {
        if (enabled && !repeatPeriodInput.value) {
          repeatPeriodInput.value = "60:00:00";
        } else if (!enabled) {
          repeatPeriodInput.value = "";
        }
      }

      updateTimesInputState();
    };

    modeRadios.forEach((radio) => {
      radio.addEventListener("change", (event) => {
        if (event.target.checked) {
          updateModeVisibility(event.target.value);
        }
      });
    });

    if (repeatCheckbox) {
      repeatCheckbox.addEventListener("change", (event) => {
        updateRepeatVisibility(event.target.checked);
      });
    }

    if (repeatTimesInput) {
      repeatTimesInput.addEventListener("change", updateTimesInputState);
    }
    if (repeatForeverInput) {
      repeatForeverInput.addEventListener("change", updateTimesInputState);
    }

    // Initial state
    updateModeVisibility(MODES.FOREVER);
    updateRepeatVisibility(repeatCheckbox ? repeatCheckbox.checked : false);
    updateTimesInputState();
  }
}

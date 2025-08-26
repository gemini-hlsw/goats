/**
 * Service for interacting with the Gemini Observatory Archive (GOA) API.
 */
class GOAService {
  /**
   * @param {API} api API client instance.
   * @param {string} targetId Target ID for fetching observations.
   */
  constructor(api, targetId) {
    this.api = api;
    this.targetId = targetId;
  }

  /**
   * Fetch observations from GOA for the given target ID.
   * @return {Promise<string[]>} Array of observation IDs.
   */
  async fetchObservations() {
    const url = `targets/${this.targetId}/observations-in-radius/`;
    const response = await this.api.get(url);
    return response.observation_ids ?? [];
  }
}

/**
 * UI widget for managing GOA observation selection and addition.
 */
class GOAWidget {
  /**
   * @param {HTMLElement} parentEl Container element for the widget.
   * @param {{api: API}} options Widget configuration.
   */
  constructor(parentEl, { api } = {}) {
    this.parentEl = parentEl;
    this.targetId = parentEl.dataset.targetId;
    this.facility = "GEM";
    this.addExistingUrl = parentEl.dataset.addExistingUrl;
    this.csrfToken = document.body.dataset.csrfToken;

    this.svc = new GOAService(api, this.targetId);

    this.isFetching = false;
    this.observations = [];
    this.selectedId = "";

    this.buildUi();
    this.hiddenForm = this.#buildHiddenForm();
    this.updateDisabled();
  }

  /**
   * Build the visible UI elements.
   */
  buildUi() {
    const row = document.createElement("div");
    row.classList.add("row", "g-3", "mb-3");

    const col = document.createElement("div");
    col.classList.add("col-12");

    const tip = document.createElement("p");
    tip.classList.add("mb-1");
    tip.textContent =
      "Search the Gemini Observatory Archive (GOA) for observations near this target's coordinates (15 arcsec search radius).";

    const group = document.createElement("div");
    group.classList.add("input-group");

    this.fetchBtn = document.createElement("button");
    this.fetchBtn.type = "button";
    this.fetchBtn.classList.add("btn", "btn-primary");
    this.fetchBtn.textContent = "Fetch From GOA";

    this.spinner = document.createElement("span");
    this.spinner.classList.add("spinner-border", "spinner-border-sm", "ms-2");
    this.spinner.style.display = "none";
    this.spinner.setAttribute("role", "status");
    this.spinner.setAttribute("aria-hidden", "true");
    this.fetchBtn.append(this.spinner);

    this.select = document.createElement("select");
    this.select.classList.add("form-select");
    this.select.innerHTML = `<option value="" selected hidden>Choose an observation…</option>`;

    this.addBtn = document.createElement("button");
    this.addBtn.type = "button";
    this.addBtn.classList.add("btn", "btn-primary");
    this.addBtn.title = "Add the selected observation for this target.";
    this.addBtn.textContent = "Add Existing Observation";

    group.append(this.fetchBtn, this.select, this.addBtn);

    this.status = document.createElement("div");
    this.status.classList.add("small", "text-muted", "my-1");

    this.error = document.createElement("div");
    this.error.classList.add("alert", "alert-danger", "py-1", "px-2", "mt-2", "d-none");
    this.error.role = "alert";

    col.append(tip, group, this.status, this.error);
    row.append(col);
    this.parentEl.append(row);

    this.fetchBtn.addEventListener("click", () => this.load());
    this.select.addEventListener("change", () => {
      this.selectedId = this.select.value;
      this.updateDisabled();
    });
    this.addBtn.addEventListener("click", () => this.add());
  }

  /**
   * Build the hidden form for adding an observation.
   * @return {HTMLFormElement} The hidden form element.
   */
  #buildHiddenForm() {
    const form = document.createElement("form");
    form.method = "POST";
    form.action = this.addExistingUrl;
    form.classList.add("d-none");

    const csrf = document.createElement("input");
    csrf.type = "hidden";
    csrf.name = "csrfmiddlewaretoken";
    csrf.value = this.csrfToken;

    const targetId = document.createElement("input");
    targetId.type = "hidden";
    targetId.name = "target_id";
    targetId.value = this.targetId;

    const facility = document.createElement("input");
    facility.type = "hidden";
    facility.name = "facility";
    facility.value = this.facility;

    const observationId = document.createElement("input");
    observationId.type = "hidden";
    observationId.name = "observation_id";

    form.append(csrf, targetId, facility, observationId);
    this.parentEl.appendChild(form);

    this.hiddenObservationInput = observationId;
    return form;
  }

  /**
   * Populate the select dropdown with observation IDs.
   * @param {string[]} ids Observation IDs.
   */
  setOptions(ids) {
    const placeholder = `<option value="" selected hidden>Choose an observation…</option>`;
    if (!ids.length) {
      this.select.innerHTML = `${placeholder}<option disabled>No observations found</option>`;
      this.selectedId = "";
      return;
    }
    this.select.innerHTML = placeholder;
    for (const id of ids) {
      if (!id) continue;
      const opt = document.createElement("option");
      opt.value = id;
      opt.textContent = id;
      this.select.append(opt);
    }
    this.selectedId = "";
  }

  /**
   * Update the status message.
   * @param {string} [msg] Status text.
   */
  setStatus(msg) {
    this.status.textContent = msg ?? "";
  }

  /**
   * Show an error message.
   * @param {string} msg Error message.
   */
  showError(msg) {
    this.error.textContent = msg;
    this.error.classList.remove("d-none");
  }

  /**
   * Clear the error message.
   */
  clearError() {
    this.error.classList.add("d-none");
    this.error.textContent = "";
  }

  /**
   * Enable/disable controls based on current state.
   */
  updateDisabled() {
    const disableAll = this.isFetching;
    this.fetchBtn.disabled = disableAll;
    this.select.disabled = disableAll || this.observations.length === 0;
    this.addBtn.disabled = disableAll || !this.selectedId;
  }

  /**
   * Fetch observations from GOA and update the UI.
   * @return {Promise<void>}
   */
  async load() {
    this.clearError();
    try {
      this.isFetching = true;
      this.spinner.style.display = "inline-block";
      this.setStatus("Fetching...");
      this.updateDisabled();

      this.observations = await this.svc.fetchObservations();
      this.setOptions(this.observations);
      this.setStatus(
        this.observations.length
          ? `Found ${this.observations.length} observation(s).`
          : "No observations found."
      );
    } catch (e) {
      console.error(e);
      let detail = "Try again.";
      if (e instanceof Response) {
        try {
          const data = await e.json();
          detail = data.detail ?? detail;
        } catch {}
      }
      this.showError(`Failed to fetch observations. ${detail}`);
      this.setStatus("");
    } finally {
      this.isFetching = false;
      this.spinner.style.display = "none";
      this.updateDisabled();
    }
  }

  /**
   * Submit the form to add the selected observation.
   */
  add() {
    if (!this.selectedId) return;
    this.isFetching = true;
    this.updateDisabled();
    this.hiddenObservationInput.value = this.selectedId;
    this.hiddenForm.submit();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const token = document.body.dataset.csrfToken;
  window.api = new API("/api/", token);
  new GOAWidget(document.getElementById("goaExistingObservationsContainer"), {
    api: window.api,
  });
});

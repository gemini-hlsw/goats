/**
 * Picks the GPP observation that automatic Gemini triggering will clone.
 *
 * Deliberately separate from ProgramObservationsPanel, which drives the
 * observation form: that panel exists to load an observation's details into a
 * form for one specific target, and carries Save / Update / Create-new
 * buttons for doing so. Here there is no target yet -- the subscription is
 * being configured before any locus has arrived -- and nothing is submitted to
 * GPP at pick time. Only two ids are recorded, to be used later once alerts
 * start arriving.
 *
 * Reuses the same read endpoints as that panel, so there is one source of
 * programme and observation data.
 */
class GPPTemplatePicker {
  #root;
  #api;
  #programSelect;
  #observationSelect;
  #summary;
  #programInput;
  #observationInput;
  #editor;
  #observationForm;
  #overridesInput;
  #workflowStateInput;
  #targetOverridesInput;
  #targetIdInput;
  #instrumentInput;
  #observations = new Map();

  /**
   * @param {!HTMLElement} root Container to render into.
   * @param {!Object} api The shared API client (window.api).
   */
  constructor(root, api) {
    this.#root = root;
    this.#api = api;
    this.#programInput = document.getElementById("id_gpp_program_id");
    this.#observationInput = document.getElementById("id_gpp_observation_id");
    this.#overridesInput = document.getElementById(
      "id_gpp_observation_overrides"
    );
    // The target half of the same Apply. Without these the picker's target
    // configuration -- its SED above all -- was collected and thrown away,
    // and automatic triggering could not reproduce what was on screen.
    this.#targetOverridesInput = document.getElementById(
      "id_gpp_target_overrides"
    );
    this.#targetIdInput = document.getElementById("id_gpp_target_id");
    this.#instrumentInput = document.getElementById("id_gpp_instrument");
    this.#workflowStateInput = document.getElementById(
      "id_gpp_workflow_state"
    );
    this.#render();
    this.#wire();
  }

  /**
   * Build the inline summary plus the offcanvas panel.
   *
   * A side panel rather than an inline block because the observation editor
   * is a full form -- instrument, exposure, conditions, constraints -- and
   * embedding that between two checkboxes would bury the rest of the
   * subscription settings. Matches the DRAGONS help panel, which is the
   * existing pattern for "detail alongside the page rather than inside it".
   *
   * Backdrop off and scrolling on, again matching DRAGONS, so the form
   * underneath stays visible and usable while the template is being chosen.
   */
  #render() {
    this.#root.innerHTML = `
      <div class="d-flex align-items-center gap-2 flex-wrap">
        <button type="button" class="btn btn-outline-secondary btn-sm"
                id="gppTemplateOpen"
                data-bs-toggle="offcanvas" data-bs-target="#gppTemplateOffcanvas">
          Choose observing template<span class="text-danger ms-1"
            title="Required when automatic Gemini triggering is on">*</span>
        </button>
        <span id="gppTemplateSummary" class="small text-muted"></span>
      </div>

      <div class="offcanvas offcanvas-end" tabindex="-1"
           id="gppTemplateOffcanvas" data-bs-scroll="true"
           data-bs-backdrop="false" aria-labelledby="gppTemplateOffcanvasTitle"
           style="width: min(46rem, 100vw);">
        <div class="offcanvas-header">
          <h5 class="offcanvas-title" id="gppTemplateOffcanvasTitle">Observing template</h5>
          <button type="button" class="btn btn-close" data-bs-dismiss="offcanvas"
                  aria-label="Close"></button>
        </div>
        <div class="offcanvas-body">
          <p class="text-muted small">
            Each ingested locus is observed by cloning this observation and
            pointing the copy at the new target. Its instrument, exposure and
            conditions carry over to every clone.
          </p>
          <div class="row g-2 mb-3">
            <div class="col-md-6">
              <label class="form-label small mb-1" for="gppTemplateProgram">Active Programs</label>
              <select id="gppTemplateProgram" class="form-select form-select-sm">
                <option value="">Loading&hellip;</option>
              </select>
            </div>
            <div class="col-md-6">
              <label class="form-label small mb-1" for="gppTemplateObservation">Approved ToO Configurations</label>
              <select id="gppTemplateObservation" class="form-select form-select-sm" disabled>
                <option value="">Select a program first</option>
              </select>
            </div>
          </div>
          <div id="gppTemplateEditor"></div>
        </div>
      </div>
    `;
    this.#programSelect = this.#root.querySelector("#gppTemplateProgram");
    this.#observationSelect = this.#root.querySelector("#gppTemplateObservation");
    this.#summary = this.#root.querySelector("#gppTemplateSummary");
    this.#editor = this.#root.querySelector("#gppTemplateEditor");
  }

  /**
   * Tell the page the applied-template state changed.
   *
   * Setting `.value` from script fires no event, so nothing outside this
   * class can observe an Apply. The ingestion page listens for this to keep
   * its submit button in step -- without it the button would stay disabled
   * after a successful Apply, or enabled after the template was cleared.
   */
  #announceTemplateState() {
    document.dispatchEvent(new CustomEvent("gpp-template-applied-changed"));
  }

  /** Attach change handlers and load the programme list. */
  #wire() {
    this.#programSelect.addEventListener("change", () => {
      const programId = this.#programSelect.value;
      this.#programInput.value = programId;
      // Clearing the observation is not just tidiness: leaving the previous
      // one selected would store an observation that does not belong to the
      // chosen programme, and the allocation check reads the programme.
      this.#observationInput.value = "";
      this.#observationSelect.value = "";
      this.#renderSummary();
      if (programId) {
        this.#loadObservations(programId);
      } else {
        this.#setObservationPlaceholder("Select a program first", true);
      }
    });

    this.#observationSelect.addEventListener("change", () => {
      this.#observationInput.value = this.#observationSelect.value;
      // Overrides describe a specific observation's fields, so carrying them
      // to a different template could apply settings that make no sense for
      // it -- or silently reintroduce values the user thought they had left
      // behind.
      this.#overridesInput.value = "";
      if (this.#workflowStateInput) {
        this.#workflowStateInput.value = "";
      }
      // Cleared together with the rest: a stale target id from a previously
      // chosen template would clone the wrong object.
      if (this.#targetOverridesInput) this.#targetOverridesInput.value = "";
      if (this.#targetIdInput) this.#targetIdInput.value = "";
      if (this.#instrumentInput) this.#instrumentInput.value = "";
      this.#renderSummary();
      this.#announceTemplateState();
      this.#renderSummary();
      this.#loadEditor(this.#observationSelect.value);
    });

    this.#loadPrograms();
  }

  /**
   * Show a single placeholder option.
   * @param {string} text
   * @param {boolean} disabled
   */
  #setObservationPlaceholder(text, disabled) {
    this.#observationSelect.innerHTML = `<option value="">${text}</option>`;
    this.#observationSelect.disabled = disabled;
  }

  /** Load the user's programmes. */
  async #loadPrograms() {
    try {
      const data = await this.#api.get("gpp/programs/");
      const matches = data?.matches ?? data?.programs?.matches ?? [];
      if (!matches.length) {
        this.#programSelect.innerHTML =
          '<option value="">No programs found</option>';
        return;
      }
      const selected = this.#programInput.value;
      this.#programSelect.innerHTML =
        '<option value="">Select a program</option>' +
        matches
          .map((p) => {
            // Same shape as the manual triggering panel, so a programme reads
            // identically in both places.
            const ref = p.reference?.label ?? p.id;
            const title = p.name ?? p.title ?? "";
            const label = title ? `${ref} - ${title}` : ref;
            const isSel = p.id === selected ? " selected" : "";
            return `<option value="${p.id}"${isSel}>${label}</option>`;
          })
          .join("");
      // Restore the saved selection so reopening the page shows the template
      // already in force, rather than an empty picker implying none is set.
      if (selected) {
        this.#loadObservations(selected);
      }
    } catch (error) {
      // Almost always missing or expired GPP credentials, so say that rather
      // than showing a bare error the user cannot act on.
      this.#programSelect.innerHTML =
        '<option value="">Could not load programs</option>';
      this.#summary.className = "small mt-2 mb-0 text-danger";
      this.#summary.textContent =
        "Could not reach GPP. Check that your GPP credentials are stored and " +
        "current.";
    }
  }

  /**
   * Load the observations belonging to one programme.
   * @param {string} programId
   */
  async #loadObservations(programId) {
    this.#setObservationPlaceholder("Loading\u2026", true);
    try {
      const data = await this.#api.get(
        `gpp/observations/?program_id=${encodeURIComponent(programId)}`
      );
      // Target-of-opportunity observations only. Automatic triggering
      // creates an observation in response to a transient alert, which is
      // what a ToO observation is for; cloning an ordinary scheduled
      // observation would produce something the programme never intended to
      // be repeated per alert.
      const groups = data?.matches ?? {};
      const too = groups.too?.results ?? [];

      if (!too.length) {
        this.#setObservationPlaceholder(
          "No approved ToO configurations in this program",
          true
        );
        return;
      }

      const option = (o) => {
        // The id is shown alongside the title because it is what identifies
        // the configuration in GPP and in trigger records -- two observations
        // in a programme can easily share a title.
        const title = o.title || o.reference?.label || "";
        const label = title ? `${o.id} - ${title}` : o.id;
        const isSel = o.id === this.#observationInput.value ? " selected" : "";
        return `<option value="${o.id}"${isSel}>${label}</option>`;
      };
      // Cached whole, exactly as the observation page does. The detail
      // endpoint (`gpp/observations/<id>/`) is a placeholder that returns a
      // different, thinner shape, which ObservationForm cannot render -- that
      // was the "could not load this observation's parameters" error. The
      // list response already carries everything the editor needs.
      this.#observations.clear();
      too.forEach((o) => this.#observations.set(o.id, o));

      this.#observationSelect.innerHTML =
        '<option value="">Select an observation</option>' +
        too.map(option).join("");
      this.#observationSelect.disabled = false;
      this.#renderSummary();
      if (this.#observationInput.value) {
        this.#loadEditor(this.#observationInput.value);
      }
    } catch (error) {
      this.#setObservationPlaceholder("Could not load observations", true);
    }
  }

  /**
   * Load the chosen observation into an editable form.
   *
   * @param {string} observationId
   */
  #loadEditor(observationId) {
    if (!observationId) {
      this.#editor.innerHTML = "";
      this.#observationForm = null;
      return;
    }
    const observation = this.#observations.get(observationId);
    if (!observation) {
      this.#editor.innerHTML = "";
      this.#observationForm = null;
      return;
    }
    try {
      this.#editor.innerHTML = "";

      // No target passed: ObservationForm defaults it to {}, and there is no
      // locus at subscription time. The target is replaced on every clone
      // anyway, so the template's own is irrelevant here.
      // mode "too", matching how the observation page builds these. The
      // form filters fields by mode (`meta.showIfMode !== this.#mode`), so
      // building a ToO configuration as "normal" shows the wrong set.
      this.#observationForm = new ObservationForm(this.#editor, {
        observation: observation,
        mode: "too",
        readOnly: false,
        callbacks: {},
        // Finder charts are prepared for a specific target, and there is no
        // target when a template is configured -- each clone gets a different
        // locus. Anything uploaded here would apply to the wrong object.
        hideSections: ["Finder Charts"],
      });

      this.#prefillObserverNotes();
      this.#lockBrightnesses();

      this.#appendSaveControls(observationId);
    } catch (error) {
      // The real error is logged and shown. The previous message said only
      // that parameters could not be loaded, which hid the actual cause -- a
      // missing Utils dependency -- behind reassuring wording and made it
      // look like a data problem rather than a broken page.
      console.error("Could not build the template editor:", error);
      this.#editor.innerHTML =
        '<div class="alert alert-warning small mb-0">Could not show this ' +
        "configuration's parameters: <code></code>. It can still be used as " +
        "a template as it stands.</div>";
      this.#editor.querySelector("code").textContent =
        error?.message ?? String(error);
      this.#observationForm = null;
    }
  }

  /**
   * Seed Observer Notes with the ANTARES link token.
   *
   * The link cannot be written now: there is no locus until an alert arrives,
   * and each clone gets a different one. So a token is placed here and
   * substituted per trigger (see `goats_tom.gemini_trigger`).
   *
   * Only seeded when the field is empty, so a PI's own notes are never
   * overwritten. Removing the token is respected -- the link is not appended
   * to notes somebody has deliberately edited.
   */
  #prefillObserverNotes() {
    // The DOM id is the field id plus its capitalized element type -- see
    // ObservationForm's `${id}${capitalizeFirstLetter(element)}` -- so
    // "observerNotes" as a textarea becomes "observerNotesTextarea". Querying
    // the bare id matched nothing and failed silently, leaving the field
    // blank. The name attribute is checked too, in case that convention
    // changes.
    const field =
      this.#editor.querySelector("#observerNotesTextarea") ??
      this.#editor.querySelector('[name="observerNotesTextarea"]') ??
      this.#editor.querySelector('[name="observerNotes"]');
    if (!field) {
      console.warn(
        "Observer Notes field not found; the ANTARES link token was not " +
          "added."
      );
      return;
    }
    if (!field.value.trim()) {
      field.value = "ANTARES locus: {locus_url}";
    }

    // Visible help text, not a placeholder: a placeholder only shows while the
    // field is empty, and this field is pre-filled, so the explanation was
    // never displayed.
    this.#addFieldHelp(
      field,
      "{locus_url} is replaced with the ANTARES page for each triggered " +
        "locus. Remove it if you do not want the link included."
    );
  }

  /**
   * Append greyed-out help text beneath a field.
   *
   * @param {!HTMLElement} field
   * @param {string} text
   */
  #addFieldHelp(field, text) {
    if (field.parentElement?.querySelector(".gpp-template-help")) {
      return;
    }
    const help = document.createElement("div");
    help.className = "form-text gpp-template-help";
    help.textContent = text;
    field.insertAdjacentElement("afterend", help);
  }

  /**
   * Make the Brightness section read-only and explain why.
   *
   * Brightness is taken from the alert that triggers each observation, so
   * anything entered here would be overwritten. Disabling the inputs makes
   * that visible rather than letting somebody carefully fill in values that
   * are then discarded.
   */
  #lockBrightnesses() {
    // Id built as `section-${heading.toLowerCase().replace(/\s+/g, "-")}`
    // from the "Brightnesses" heading in fields.js -- note the plural, which
    // is easy to get wrong and fails silently.
    const section = this.#editor.querySelector("#section-brightnesses");
    if (!section) {
      console.warn(
        "Brightnesses section not found; it was not made read-only."
      );
      return;
    }
    // `inert` rather than `disabled`: a disabled input is omitted from
    // FormData, so disabling this section silently dropped its fields from
    // the payload and the serializer rejected the request. `inert` makes the
    // section non-interactive and unfocusable while leaving its values
    // submittable -- which matters because they are still valid values, just
    // ones the trigger will replace.
    section.inert = true;
    if (!("inert" in section)) {
      section.style.pointerEvents = "none";
      section
        .querySelectorAll("input, select, textarea, button")
        .forEach((el) => el.setAttribute("tabindex", "-1"));
    }
    section.style.opacity = "0.6";

    const note = document.createElement("div");
    note.className = "form-text";
    note.textContent =
      "Set automatically from each alert's newest magnitude and passband.";
    section.prepend(note);
  }

  /**
   * Add the save control and its warning beneath the editor.
   *
   * @param {string} observationId
   */
  #appendSaveControls(observationId) {
    const bar = document.createElement("div");
    bar.className = "d-flex align-items-center gap-2 mt-3 flex-wrap";
    bar.innerHTML = `
      <button type="button" class="btn btn-primary btn-sm" id="gppTemplateSave">
        Apply these settings
      </button>
      <span id="gppTemplateSaveStatus" class="small"></span>
    `;
    this.#editor.appendChild(bar);

    const button = bar.querySelector("#gppTemplateSave");
    const statusEl = bar.querySelector("#gppTemplateSaveStatus");

    // The button reports its own state, so no sentence beside it repeats
    // what it already says. Three states: ready to apply, applying, applied.
    const setApplied = (applied) => {
      button.disabled = applied;
      button.classList.toggle("btn-primary", !applied);
      button.classList.toggle("btn-outline-success", applied);
      button.textContent = applied
        ? "\u2713 Applied"
        : "Apply these settings";
    };

    // Edit anything in the panel and it is no longer applied. Without this
    // the button would still read "Applied" after a scheduling window was
    // changed -- a confident label for a stale state, which is worse than
    // the sentence it replaced.
    this.#editor.addEventListener("input", () => setApplied(false));
    this.#editor.addEventListener("change", () => setApplied(false));

    button.addEventListener("click", async () => {
      button.disabled = true;
      statusEl.className = "small text-muted";
      statusEl.textContent = "Applying\u2026";
      try {
        // getData() returns a FormData, matching what the observation page
        // posts, so the backend's existing _normalize_form_data handles it
        // unchanged. Posted without JSON stringification for the same reason.
        const payload = this.#observationForm.getData();
        if (!payload) {
          throw new Error("The observation form is not ready.");
        }
        payload.append("gppObservationId", observationId);

        // The template's own target and observing mode, taken from the
        // cached observation. They cannot be derived from this form: it
        // describes an observation, and the page has no GOATS target at all
        // -- the picker is configuring a template, not observing something.
        // Read via ContextSerializer instead, they came back empty on every
        // Apply, since that serializer requires a GOATS target primary key.
        const cached = this.#observations.get(observationId) || {};
        const asterism = cached.targetEnvironment?.asterism ?? [];
        payload.append("templateTargetId", asterism[0]?.id ?? "");
        payload.append(
          "templateInstrument",
          cached.observingMode?.mode ?? cached.instrument ?? ""
        );

        // Validated and converted server-side, never written to GPP. Doing
        // the conversion there reuses ObservationSerializer, so what is
        // stored is guaranteed to be a shape GPP will accept -- finding out
        // otherwise at trigger time would mean a failure once per alert.
        const result = await this.#api.post(
          "gpp/observations/serialize-overrides/",
          payload,
          {},
          false
        );
        this.#overridesInput.value = JSON.stringify(result?.overrides ?? {});
        // Stored separately: the workflow state is not an observation
        // property, it is applied by its own mutation after the clone.
        if (this.#workflowStateInput) {
          this.#workflowStateInput.value = result?.workflowState ?? "";
        }
        if (this.#targetOverridesInput) {
          this.#targetOverridesInput.value = JSON.stringify(
            result?.targetOverrides ?? {}
          );
        }
        if (this.#targetIdInput) {
          this.#targetIdInput.value = result?.gppTargetId ?? "";
        }
        if (this.#instrumentInput) {
          this.#instrumentInput.value = result?.instrument ?? "";
        }
        this.#renderSummary();
      this.#announceTemplateState();
        setApplied(true);
        statusEl.textContent = "";
      } catch (error) {
        // api.js throws the Response itself on a non-2xx, so the server's
        // explanation is available and worth showing. The previous message
        // said only "Could not apply these settings", which hid a specific,
        // actionable validation error behind a generic one.
        let detail = "";
        try {
          if (error instanceof Response) {
            const body = await error.json();
            detail = body?.detail ?? JSON.stringify(body);
          } else {
            detail = error?.message ?? String(error);
          }
        } catch (parseError) {
          detail = `HTTP ${error?.status ?? "error"}`;
        }
        console.error("Could not apply template settings:", detail, error);
        statusEl.className = "small text-danger";
        statusEl.textContent = `Could not apply these settings: ${detail}`;
        // Back to "Apply these settings", not left disabled: nothing was
        // applied, and the PI needs to be able to try again. Deliberately not
        // in a `finally` -- that would re-enable the button on success too,
        // undoing the applied state it had just set.
        setApplied(false);
      }
    });
  }

  /** Describe the current selection, or what is still missing. */
  #renderSummary() {
    const hasProgram = Boolean(this.#programInput.value);
    const hasObservation = Boolean(this.#observationInput.value);

    if (!hasProgram || !hasObservation) {
      this.#summary.className = "small text-muted";
      this.#summary.textContent =
        "Pick a program and ToO configuration to use as the template.";
      return;
    }

    // Selected is not applied, and the difference decides whether ingestion
    // can start -- so the one line next to the button says which, rather
    // than describing what cloning will do. Applied state is read from the
    // hidden fields because they are what actually gets submitted; anything
    // else would be reporting an intention rather than a fact.
    const label = (
      this.#observationSelect.selectedOptions[0]?.textContent ?? ""
    ).trim();
    const applied = Boolean(
      this.#targetIdInput?.value && this.#instrumentInput?.value
    );

    if (applied) {
      this.#summary.className = "small text-success";
      this.#summary.textContent = `\u2713 Applied \u00b7 cloning \u201c${label}\u201d`;
    } else {
      this.#summary.className = "small text-warning";
      this.#summary.textContent = `Not applied \u00b7 open the panel and click Apply to use \u201c${label}\u201d`;
    }
  }
}

/**
 * BLANCO observation form, drawn in the browser from the API's description.
 *
 * The Django form declares what can be asked for; this draws it, section by
 * section, in the accordion the GPP form uses.
 */
class BlancoObservationForm {
  static ENDPOINT = "/api/blanco/observations/";

  /** The grid the form and every section body sit on. */
  static GRID = "row g-3";

  /**
   * The one scale the form is spaced on, so no gap is anybody's guess.
   *
   * `section` opens a section of the form and `nested` one held inside
   * another; both are given the same room above their title. Below it they
   * are not: `nestedBody` holds a nested title closer to what it names than
   * `body` does, so the two read as one block and not as two. A repeated
   * body takes nothing at all: its tabs bring half a rem of padding over the
   * label, which is that gap already.
   */
  static SPACE = {
    section: "mt-4",
    nested: "mt-4",
    body: "mt-2",
    nestedBody: "mt-1",
    tabs: "mt-0",
  };

  /** What this form is for, said once at the top. */
  static DESCRIPTION =
    "Submit an imaging observation to the Blanco 4-metre telescope at Cerro " +
    "Tololo, through the LCO observation portal. Fill in the request " +
    "details, then the configuration and the exposures it takes.";

  #container;
  #targetId;
  #structure = null;
  /** How to narrow each configuration, by the pane it belongs to. */
  #narrowers = new WeakMap();
  /** How to label each exposure, by the pane it belongs to. */
  #labellers = new WeakMap();
  /** The control that says which proposal buys the time. */
  #proposal = null;
  /** The proposal the configurations on show were filled in for. */
  #paidFor = null;
  /** What was filled in under each proposal, so going back brings it back. */
  #kept = new Map();

  /**
   * @param {HTMLElement} container Element carrying `data-target-id`.
   */
  constructor(container) {
    this.#container = container;
    this.#targetId = container.dataset.targetId;
  }

  /**
   * Load the form's description and draw it.
   *
   * @returns {Promise<void>}
   */
  async init() {
    try {
      const response = await fetch(
        `${BlancoObservationForm.ENDPOINT}?target_id=${this.#targetId}`,
        { credentials: "same-origin" },
      );
      if (!response.ok) {
        throw new Error(`The form could not be loaded (${response.status}).`);
      }
      this.#structure = await response.json();
    } catch (error) {
      this.#announce(error.message, "danger");
      return;
    }
    this.#draw();
  }

  /**
   * @private
   * @returns {void}
   */
  #draw() {
    const form = document.createElement("form");
    form.className = BlancoObservationForm.GRID;
    // Nothing is posted from here: the buttons say what happens.
    form.addEventListener("submit", (event) => event.preventDefault());
    (this.#structure.sections ?? []).forEach((section) => {
      const { header, body } = this.#section(section);
      form.append(header, body);
    });
    form.append(this.#actions());
    this.#container.replaceChildren(
      this.#blurb(),
      document.createElement("hr"),
      form,
      this.#messages(),
    );
    this.#followProposal();
  }

  /**
   * Show only the parameters the chosen instrument accepts.
   *
   * The form carries a field for every parameter any instrument declares,
   * because the instrument is not known until it is picked: DECam centres on
   * one of three detectors and does not dither at all, while NEWFIRM dithers
   * through a sequence and centres on one of four. The portal's schema says
   * which parameters apply, and which values each takes.
   *
   * @private
   * @param {HTMLElement} form
   * @returns {void}
   */
  #followInstrument(pane, tab) {
    const select = pane.querySelector('[data-field$="_instrument_type"] select');
    if (!select) {
      return;
    }
    const apply = () => {
      // The proposal is what buys the time, so it says which instruments
      // this configuration may spend it on.
      BlancoObservationForm.narrow(select.closest("[data-field]"), {
        allowed: this.#instrumentsAllowed(),
      });
      const accepted = this.#structure.instruments?.[select.value] ?? {};
      pane.querySelectorAll("[data-field]").forEach((column) => {
        const suffix = BlancoObservationForm.suffixOf(column.dataset.field);
        // The instrument is not one of its own parameters: narrowed here it
        // would be handed back every option the proposal has no time on.
        if (suffix === "instrument_type") {
          return;
        }
        const spec = accepted[suffix];
        // A parameter the instrument never declared does not apply to it.
        if (suffix.startsWith("extra_")) {
          column.classList.toggle("d-none", !spec);
        }
        BlancoObservationForm.narrow(column, spec ?? {});
      });
      // The tab has to say what is inside it, or it says nothing at all.
      // The name is short already: the form takes the telescope off every
      // option, since every instrument here is on the same one.
      const chosen = select.options[select.selectedIndex];
      const instrument = chosen?.textContent.trim();
      tab.textContent = instrument
        ? `${pane.dataset.instance} · ${instrument}`
        : pane.dataset.instance;
      // Narrowing may have taken a filter this instrument does not carry.
      pane
        .querySelectorAll('[data-role="exposure"]')
        .forEach((exposure) => this.#labellers.get(exposure)?.());
    };
    select.addEventListener("change", apply);
    this.#narrowers.set(pane, apply);
    apply();
  }

  /** The instruments the chosen proposal has time on, if it says. */
  #instrumentsAllowed() {
    return this.#structure.proposals?.[this.#proposal?.value] ?? [];
  }

  /**
   * Put every configuration on show to the proposal that pays for it.
   *
   * @private
   * @returns {void}
   */
  #settle() {
    this.#container
      .querySelectorAll('[data-role="configuration"]')
      .forEach((pane) => this.#narrowers.get(pane)?.());
  }

  /**
   * Keep every configuration to what the chosen proposal may observe with.
   *
   * The instrument is picked one configuration at a time, and the proposal
   * once for the whole request: changed, it has to reach the configurations
   * drawn before it. A proposal named by no instrument holds them to none.
   *
   * @private
   * @returns {void}
   */
  #followProposal() {
    this.#proposal = this.#container.querySelector('[data-field="proposal"] select');
    this.#paidFor = this.#paidFor ?? this.#proposal?.value ?? null;
    this.#proposal?.addEventListener("change", () => this.#changeProposal());
    // The configurations were drawn before the form was put on the page, so
    // nothing had asked the proposal what it allows.
    this.#settle();
  }

  /**
   * Follow the proposal to the configurations it can pay for.
   *
   * Time is given on an instrument, so a proposal that has none on the one
   * a configuration names cannot observe what was filled in for it -- and
   * neither can the configurations beside it, which is a form to be gone
   * through again field by field. The request starts again instead, with
   * the one configuration a form is drawn with; what it had is put away
   * under the proposal it was filled in for, and comes back with it.
   *
   * @private
   * @returns {void}
   */
  #changeProposal() {
    const now = this.#proposal.value;
    const before = this.#paidFor;
    this.#paidFor = now;
    if (before === now) {
      return;
    }
    if (this.#affordable()) {
      // Every instrument on show is one this proposal has time on: there is
      // nothing to put away, and nothing to draw again.
      this.#settle();
      return;
    }
    if (before !== null) {
      this.#kept.set(before, this.#configurations());
    }
    this.#again(this.#kept.get(now) ?? null);
  }

  /** Whether this proposal has time on every instrument now on show. */
  #affordable() {
    const allowed = this.#instrumentsAllowed();
    if (!allowed.length) {
      return true;
    }
    return [
      ...this.#container.querySelectorAll(
        '[data-role="configuration"] [data-field$="_instrument_type"] select',
      ),
    ].every((select) => allowed.includes(select.value));
  }

  /**
   * Draw the request again, keeping what the proposal did not pay for.
   *
   * @private
   * @param {?{counts: number[], values: Object}} kept What was put away for
   *   the proposal now chosen, or null where it has never been filled in.
   * @returns {void}
   */
  #again(kept) {
    const request = this.#request();
    this.#draw();
    this.#restore(request);
    if (kept) {
      this.#restoreConfigurations(kept);
    }
    this.#settle();
  }

  /**
   * What the request asks for outside its configurations: its name, its
   * proposal, the window it is observed in and the cadence it repeats on.
   *
   * @private
   * @returns {Object}
   */
  #request() {
    return this.#read((name) => !name.startsWith("c_"));
  }

  /**
   * What every configuration on show was filled in with, and how many of
   * them, and of the exposures each carries, there were to fill in.
   *
   * @private
   * @returns {{counts: number[], values: Object}}
   */
  #configurations() {
    return {
      counts: [
        ...this.#container.querySelectorAll('[data-role="configuration"]'),
      ].map((pane) => pane.querySelectorAll('[data-role="exposure"]').length),
      values: this.#read((name) => name.startsWith("c_")),
    };
  }

  /**
   * The value of every control the form holds, by the name it posts under.
   *
   * @private
   * @param {function(string): boolean} wanted
   * @returns {Object}
   */
  #read(wanted) {
    const values = {};
    this.#container.querySelectorAll("input, select, textarea").forEach((input) => {
      if (input.name && wanted(input.name)) {
        values[input.name] =
          input.type === "checkbox" ? input.checked : input.value;
      }
    });
    return values;
  }

  /**
   * Put back what was read, into the controls that are there to take it.
   *
   * @private
   * @param {Object} values
   * @returns {void}
   */
  #restore(values) {
    Object.entries(values).forEach(([name, value]) => {
      const input = this.#container.querySelector(`[name="${name}"]`);
      if (input) {
        BlancoField.write(input, value);
      }
    });
  }

  /**
   * Draw as many configurations, and as many exposures in each, as were put
   * away, and fill them in again.
   *
   * @private
   * @param {{counts: number[], values: Object}} kept
   * @returns {void}
   */
  #restoreConfigurations({ counts, values }) {
    this.#drawUpTo(this.#container, "configuration", counts.length);
    [...this.#container.querySelectorAll('[data-role="configuration"]')].forEach(
      (pane, index) => this.#drawUpTo(pane, "exposure", counts[index] ?? 1),
    );
    this.#restore(values);
  }

  /**
   * Ask for as many of something as there were, one at a time.
   *
   * @private
   * @param {HTMLElement} within
   * @param {string} role
   * @param {number} wanted
   * @returns {void}
   */
  #drawUpTo(within, role, wanted) {
    const add = within.querySelector(`[data-role="add-${role}"]`);
    const drawn = () => within.querySelectorAll(`[data-role="${role}"]`).length;
    while (add && drawn() < wanted) {
      const before = drawn();
      add.click();
      // The facility allows only so many, and the button says so by going
      // spent: asked past that, nothing is drawn and nothing is waited for.
      if (drawn() === before) {
        return;
      }
    }
  }

  /**
   * Say on the tab which filter this exposure is taken through.
   *
   * One exposure is told from the next by what it looks through, so the
   * number on its own names nothing. The filter can also be changed for it,
   * by the instrument the configuration settles on, which is why the label
   * is refreshed as well as listened for.
   *
   * @private
   * @param {HTMLElement} pane
   * @param {HTMLElement} tab
   * @returns {void}
   */
  #followFilter(pane, tab) {
    const select = pane.querySelector('[data-field$="_filter"] select');
    const label = () => {
      const filter = select?.value
        ? select.options[select.selectedIndex].textContent.trim()
        : "";
      tab.textContent = filter
        ? `${pane.dataset.instance} · ${filter}`
        : pane.dataset.instance;
    };
    select?.addEventListener("change", label);
    this.#labellers.set(pane, label);
    label();
  }

  /**
   * What a field is, with the configuration and exposure it belongs to
   * stripped off: `c_1_ic_1_exposure_time` is an `exposure_time`.
   *
   * @param {string} name
   * @returns {string}
   */
  static suffixOf(name) {
    return name.replace(/^c_\d+_(ic_\d+_)?/, "");
  }

  /**
   * Keep a control to what one instrument takes.
   *
   * @param {HTMLElement} column
   * @param {Object} spec What the instrument declares for this parameter.
   * @returns {void}
   */
  static narrow(column, spec) {
    const input = column.querySelector("input, select");
    if (!input) {
      return;
    }
    if (input.tagName === "SELECT") {
      const allowed = (spec.allowed ?? []).map(String);
      let valid = false;
      [...input.options].forEach((option) => {
        // With nothing declared the field is not the instrument's to limit.
        const keep = !allowed.length || allowed.includes(option.value);
        option.hidden = !keep;
        option.disabled = !keep;
        valid = valid || (keep && option.value === input.value);
      });
      if (!valid) {
        // The value belonged to the instrument that was chosen before.
        input.value =
          spec.default !== undefined ? String(spec.default) : allowed[0] ?? "";
        // Nothing was typed, so nothing was raised: say the value moved.
        BlancoField.recheck(input);
      }
    }
    ["min", "max"].forEach((bound) => {
      if (spec[bound] === undefined) {
        input.removeAttribute(bound);
      } else {
        input.setAttribute(bound, spec[bound]);
      }
    });
  }

  /**
   * The description the form opens with, laid out as the GPP form lays out
   * its own: a full-width row above the rule.
   *
   * @private
   * @returns {HTMLElement}
   */
  #blurb() {
    const row = document.createElement("div");
    // The rule below collapses its own margin into this one, so the text
    // needs the larger of the two to breathe.
    row.className = "row g-3 mb-4";
    row.dataset.role = "description";
    const column = document.createElement("div");
    column.className = "col-12";
    const text = document.createElement("p");
    text.className = "mb-0 fst-italic";
    text.textContent = BlancoObservationForm.DESCRIPTION;
    column.append(text);
    row.append(column);
    return row;
  }

  /**
   * A section header and the body under it.
   *
   * A top-level section is the accordion the GPP form uses, header and
   * chevron alike. One nested inside another is not: it is a titled block
   * that stays open, since the section holding it already collapses.
   *
   * @private
   * @param {{title: string, open: boolean, fields: Object[],
   *   sections: Object[]}} section
   * @param {boolean} [collapsible]
   * @returns {{header: HTMLElement, body: HTMLElement}}
   */
  #section(section, collapsible = true) {
    const collapseId = `section-${section.title.toLowerCase().replace(/\s+/g, "-")}`;

    const space = BlancoObservationForm.SPACE;
    const header = document.createElement("div");
    header.className = `d-flex align-items-center justify-content-between ${
      collapsible ? space.section : space.nested
    } mb-0`;
    header.dataset.role = "section";
    header.dataset.section = collapseId;

    // A nested title is subordinate to the section holding it, and has to
    // read that way: it carries no chevron, so the weight is all that tells
    // the two apart.
    const heading = document.createElement(collapsible ? "h5" : "h6");
    heading.className = collapsible
      ? "mb-0"
      : "mb-0 fw-semibold text-uppercase text-body-secondary";
    heading.textContent = section.title;
    header.append(heading);

    const body = document.createElement("div");
    body.className = `${BlancoObservationForm.GRID} ${
      section.instances ? space.tabs : collapsible ? space.body : space.nestedBody
    }`;
    body.id = collapseId;
    body.dataset.role = "section-body";
    (section.fields ?? []).forEach((field) => body.append(BlancoField.build(field)));
    // A section can hold sections: the portal puts the exposures inside the
    // configuration they belong to, and the cadence inside its window.
    (section.sections ?? []).forEach((child) => {
      const nested = this.#section(child, false);
      body.append(nested.header, nested.body);
    });
    if (section.instances) {
      body.append(this.#repeated(section));
    }

    if (collapsible) {
      body.classList.add("collapse");
      body.classList.toggle("show", Boolean(section.open));
      const toggle = this.#toggle(collapseId, body, Boolean(section.open));
      header.append(toggle);
      // The title is as good a place to click as the chevron itself.
      header.addEventListener("click", (event) => {
        if (!toggle.contains(event.target)) {
          toggle.click();
        }
      });
    }
    return { header, body };
  }

  /**
   * A section whose content repeats: one numbered tab per instance.
   *
   * Every instance the facility allows is described, but only the ones asked
   * for are drawn -- and only what is drawn is ever sent, so a configuration
   * nobody filled in is never built.
   *
   * @private
   * @param {{repeat: string, instances: Object[]}} section
   * @returns {HTMLElement}
   */
  #repeated(section) {
    const role = section.repeat;
    const block = document.createElement("div");
    block.className = "col-12";
    block.dataset.role = `${role}-list`;

    const tabs = BlancoObservationForm.tabStrip(`${role}-tabs`);
    const panes = document.createElement("div");
    panes.className = "tab-content";
    panes.dataset.role = `${role}-panes`;

    const add = BlancoObservationForm.iconButton(
      `add-${role}`,
      "plus",
      `Add ${role}`,
      "success",
      () => this.#add(section, block),
    );
    const remove = BlancoObservationForm.iconButton(
      `remove-${role}`,
      "trash",
      `Remove this ${role}`,
      "danger",
      () => this.#remove(section, block),
    );
    block.append(BlancoObservationForm.tabLine(tabs, [add, remove]), panes);

    this.#drawInstance(section, block, section.instances[0]);
    return block;
  }

  /**
   * Draw one instance and bring it to the front.
   *
   * @private
   * @param {Object} section
   * @param {HTMLElement} block
   * @param {Object} instance
   * @returns {void}
   */
  #drawInstance(section, block, instance) {
    const role = section.repeat;
    const item = document.createElement("li");
    item.className = "nav-item";
    item.dataset.role = `${role}-tab`;
    item.dataset.instance = instance.id;
    const tab = document.createElement("button");
    tab.type = "button";
    tab.className = "nav-link";
    tab.textContent = instance.id;
    tab.addEventListener("click", () => this.#show(block, role, instance.id));
    item.append(tab);

    const pane = document.createElement("div");
    // Not a row itself: Bootstrap shows a pane with `display: block`, which
    // beats the `display: flex` a row needs, and every column would then
    // take a line of its own. The grid goes inside instead.
    pane.className = "tab-pane";
    pane.dataset.role = role;
    pane.dataset.instance = instance.id;
    const row = document.createElement("div");
    row.className = BlancoObservationForm.GRID;
    (instance.fields ?? []).forEach((field) => row.append(BlancoField.build(field)));
    pane.append(row);
    (instance.sections ?? []).forEach((child) => {
      const nested = this.#section(child, false);
      pane.append(nested.header, nested.body);
    });

    block.querySelector(`[data-role="${role}-tabs"]`).append(item);
    block.querySelector(`[data-role="${role}-panes"]`).append(pane);
    this.#show(block, role, instance.id);
    if (role === "configuration") {
      this.#followInstrument(pane, tab);
    } else {
      this.#followFilter(pane, tab);
      // An exposure drawn now was not there when its configuration chose an
      // instrument, so nothing had narrowed it: it would offer every value
      // every instrument takes.
      this.#narrowers.get(block.closest('[data-role="configuration"]'))?.();
    }
    this.#refresh(section, block);
  }

  /**
   * @private
   * @param {Object} section
   * @param {HTMLElement} block
   * @returns {void}
   */
  #add(section, block) {
    const drawn = block.querySelectorAll(`[data-role="${section.repeat}"]`).length;
    const next = section.instances[drawn];
    if (next) {
      this.#drawInstance(section, block, next);
    }
  }

  /**
   * @private
   * @param {Object} section
   * @param {HTMLElement} block
   * @returns {void}
   */
  #remove(section, block) {
    const role = section.repeat;
    const panes = [...block.querySelectorAll(`[data-role="${role}"]`)];
    if (panes.length < 2) {
      return;
    }
    // The last drawn is the one that goes: the numbers a request is built
    // from have to stay unbroken.
    const last = panes[panes.length - 1];
    const id = last.dataset.instance;
    block
      .querySelector(`[data-role="${role}-tab"][data-instance="${id}"]`)
      ?.remove();
    last.remove();
    this.#show(block, role, panes[panes.length - 2].dataset.instance);
    this.#refresh(section, block);
  }

  /**
   * Bring one instance to the front.
   *
   * @private
   * @param {HTMLElement} block
   * @param {string} role
   * @param {number|string} id
   * @returns {void}
   */
  #show(block, role, id) {
    block.querySelectorAll(`[data-role="${role}-tab"]`).forEach((tab) => {
      const chosen = String(tab.dataset.instance) === String(id);
      tab.querySelector(".nav-link").classList.toggle("active", chosen);
    });
    block.querySelectorAll(`[data-role="${role}"]`).forEach((pane) => {
      const chosen = String(pane.dataset.instance) === String(id);
      pane.classList.toggle("show", chosen);
      pane.classList.toggle("active", chosen);
    });
  }

  /**
   * Spend the buttons that have nothing left to do.
   *
   * @private
   * @param {Object} section
   * @param {HTMLElement} block
   * @returns {void}
   */
  #refresh(section, block) {
    const drawn = block.querySelectorAll(`[data-role="${section.repeat}"]`).length;
    const add = block.querySelector(`[data-role="add-${section.repeat}"]`);
    add.disabled = drawn >= section.instances.length;
    const remove = block.querySelector(`[data-role="remove-${section.repeat}"]`);
    remove.disabled = drawn < 2;
    // A button that can do nothing says nothing: the colour is for what it
    // would do, so it goes while there is nothing to do.
    BlancoObservationForm.colour(add, "success");
    BlancoObservationForm.colour(remove, "danger");
  }

  /**
   * Paint a button for what it does, or grey it while it can do nothing.
   *
   * @param {HTMLElement} button
   * @param {string} variant
   * @returns {void}
   */
  static colour(button, variant) {
    button.classList.toggle(`btn-outline-${variant}`, !button.disabled);
    button.classList.toggle("btn-outline-secondary", button.disabled);
  }

  /**
   * The line a strip of tabs sits on, with what acts on them at the end.
   *
   * @param {HTMLElement} strip
   * @param {HTMLElement[]} actions
   * @returns {HTMLElement}
   */
  static tabLine(strip, actions) {
    const line = document.createElement("div");
    line.className =
      "d-flex align-items-end justify-content-between border-bottom mb-3";
    const buttons = document.createElement("div");
    buttons.className = "d-flex gap-1 mb-2";
    buttons.append(...actions);
    line.append(strip, buttons);
    return line;
  }

  /**
   * @param {string} role
   * @returns {HTMLElement}
   */
  static tabStrip(role) {
    const strip = document.createElement("ul");
    strip.className = "nav nav-underline";
    strip.dataset.role = role;
    return strip;
  }

  /**
   * A button that says what it does with an icon alone.
   *
   * @param {string} role
   * @param {string} icon A FontAwesome solid icon, the only set GOATS ships.
   * @param {string} label
   * @param {string} variant What it does, said in colour.
   * @param {function(): void} onClick
   * @returns {HTMLElement}
   */
  static iconButton(role, icon, label, variant, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `btn btn-sm btn-outline-${variant}`;
    button.dataset.role = role;
    button.title = label;
    button.setAttribute("aria-label", label);
    button.innerHTML = `<i class="fa-solid fa-${icon}"></i>`;
    button.addEventListener("click", onClick);
    return button;
  }

  /**
   * The chevron that opens and closes a section.
   *
   * @private
   * @param {string} collapseId
   * @param {HTMLElement} body
   * @param {boolean} open
   * @returns {HTMLElement}
   */
  #toggle(collapseId, body, open) {
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "btn p-0";
    toggle.dataset.role = "section-toggle";
    toggle.dataset.section = collapseId;
    toggle.setAttribute("data-bs-toggle", "collapse");
    toggle.setAttribute("data-bs-target", `#${collapseId}`);
    toggle.setAttribute("aria-controls", collapseId);

    BlancoObservationForm.markExpanded(toggle, open);
    body.addEventListener("show.bs.collapse", () =>
      BlancoObservationForm.markExpanded(toggle, true),
    );
    body.addEventListener("hide.bs.collapse", () =>
      BlancoObservationForm.markExpanded(toggle, false),
    );
    return toggle;
  }

  /**
   * Point a section's chevron the way the section is going.
   *
   * @param {HTMLElement} toggle
   * @param {boolean} expanded
   * @returns {void}
   */
  static markExpanded(toggle, expanded) {
    toggle.setAttribute("aria-expanded", String(expanded));
    toggle.innerHTML = `<i class="fa-solid fa-chevron-${
      expanded ? "up" : "down"
    }"></i>`;
  }

  /**
   * Read every control on show.
   *
   * @returns {Object} Field names mapped to their values.
   */
  collect() {
    const fields = {};
    this.#container.querySelectorAll("input, select, textarea").forEach((input) => {
      // A hidden field is one this request does not take.
      if (input.name && !input.closest(".d-none")) {
        Object.assign(fields, BlancoField.read(input));
      }
    });
    return fields;
  }

  /**
   * The two buttons the form ends on.
   *
   * @private
   * @returns {HTMLElement}
   */
  #actions() {
    const row = document.createElement("div");
    row.className = `col-12 d-flex justify-content-end gap-2 ${BlancoObservationForm.SPACE.section}`;
    row.dataset.role = "actions";
    row.append(
      BlancoObservationForm.action(
        "validate",
        "Validate",
        "btn btn-outline-primary",
        () => this.#run("validate"),
      ),
      BlancoObservationForm.action("submit", "Submit", "btn btn-primary", () =>
        this.#run("submit"),
      ),
    );
    return row;
  }

  /**
   * @param {string} role
   * @param {string} label
   * @param {string} className
   * @param {Function} onClick
   * @returns {HTMLElement}
   */
  static action(role, label, className, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.dataset.role = role;
    button.textContent = label;
    button.addEventListener("click", onClick);
    return button;
  }

  /**
   * Validate, or submit -- which is validating and then going through with
   * it. Both ask the same question first, so both ask it the same way.
   *
   * @private
   * @param {string} action
   * @returns {Promise<void>}
   */
  async #run(action) {
    const buttons = [
      ...this.#container.querySelectorAll(
        '[data-role="validate"], [data-role="submit"]',
      ),
    ];
    buttons.forEach((button) => (button.disabled = true));
    this.#clearErrors();
    try {
      const answer = await this.#check();
      if (!answer.valid) {
        this.#showErrors(answer.errors);
      } else if (action === "submit") {
        // The page is on its way out; the buttons stay spent behind it.
        this.#post();
        return;
      } else {
        this.#announce(
          answer.message || "This observation is valid.",
          "success",
          "Valid",
        );
      }
    } catch (error) {
      this.#announce(error.message, "danger");
    }
    buttons.forEach((button) => (button.disabled = false));
  }

  /**
   * Ask the form itself whether what was filled in would be accepted.
   *
   * @private
   * @returns {Promise<Object>}
   */
  async #check() {
    const response = await fetch(BlancoObservationForm.ENDPOINT, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": BlancoObservationForm.token(),
      },
      body: JSON.stringify({
        target_id: this.#targetId,
        fields: this.collect(),
      }),
    });
    if (!response.ok) {
      throw new Error(`The form could not be checked (${response.status}).`);
    }
    return response.json();
  }

  /**
   * Hand the form to the toolkit's own view, which submits the observation
   * and keeps the record of it. Only a form already found sound gets here,
   * so what comes back is the target's page and not this one again -- which
   * would be drawn empty, and everything filled in lost with it.
   *
   * @private
   * @returns {void}
   */
  #post() {
    const form = document.createElement("form");
    form.method = "post";
    form.action = window.location.href;
    form.className = "d-none";
    const fields = {
      ...this.collect(),
      ...(this.#structure.hidden ?? {}),
      csrfmiddlewaretoken: BlancoObservationForm.token(),
    };
    Object.entries(fields).forEach(([name, value]) => {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = name;
      input.value = value ?? "";
      form.append(input);
    });
    document.body.append(form);
    form.submit();
  }

  /**
   * @returns {string}
   */
  static token() {
    return document.body?.dataset?.csrfToken ?? "";
  }

  /**
   * Put each message under the field it was raised on.
   *
   * @private
   * @param {Object} errors
   * @returns {void}
   */
  #showErrors(errors) {
    let first = null;
    const loose = [];
    // The whole answer, keys and all, for whoever is looking into it.
    console.warn("Blanco form errors", errors);
    Object.entries(errors ?? {}).forEach(([name, messages]) => {
      const said = [].concat(messages);
      const slot = this.#container.querySelector(`[data-error-for="${name}"]`);
      if (!slot) {
        // Raised on the request as a whole, or on a field never drawn. Each
        // is about a part of its own, and reads as one where it is listed.
        said.forEach((message) =>
          loose.push(BlancoObservationForm.plainly(message)),
        );
        return;
      }
      slot.textContent = said.join(" ");
      slot.classList.remove("d-none");
      const column = slot.closest("[data-field]");
      column?.querySelector("input, select, textarea")?.classList.add("is-invalid");
      first = first ?? column;
    });
    const said = loose.filter(Boolean);
    // Said from a toast at the foot of the page, which is nowhere near the
    // fields it is about: what to look for, not where to look.
    this.#announce(
      said.length
        ? "The portal would not take this request."
        : "Check the fields marked in red.",
      "danger",
      "Not ready",
    );
    this.#refusal(said);
    if (first) {
      this.#reveal(first);
    }
  }

  /**
   * What was refused of the request as a whole, kept where it can be read.
   *
   * A toast says one thing and goes. The portal refuses several at a time,
   * each about a part of the request -- a configuration, an exposure, the
   * window -- and they are worth reading one under another, beside the form
   * they are about, for as long as they are true of it.
   *
   * @private
   * @param {string[]} messages
   * @returns {void}
   */
  #refusal(messages) {
    const slot = this.#container.querySelector('[data-role="messages"]');
    if (!slot) {
      return;
    }
    slot.querySelector('[data-role="refusal"]')?.remove();
    if (!messages.length) {
      return;
    }
    const alert = document.createElement("div");
    alert.className = "alert alert-danger mt-3";
    alert.dataset.role = "refusal";
    const said = document.createElement("p");
    said.className = "fw-semibold mb-2";
    said.textContent = "The portal would not take this request:";
    const list = document.createElement("ul");
    list.className = "mb-0 ps-3";
    messages.forEach((message) => {
      const item = document.createElement("li");
      item.textContent = message;
      list.append(item);
    });
    alert.append(said, list);
    slot.append(alert);
  }

  /**
   * Say a message the way it would be said out loud.
   *
   * The toolkit hands the portal's answer over as `key: message` chains, and
   * the key it uses for "this is about the request, not about a field" is
   * `non_field_errors` -- machinery, which names nothing to whoever is
   * reading it. It stays in the log, where it is worth having.
   *
   * @param {string} text
   * @returns {string}
   */
  static plainly(text) {
    return String(text)
      .replace(/\bnon_field_errors\s*:\s*/g, "")
      .replace(/\s+/g, " ")
      .replace(/^[\s'"[\]]+|[\s'"[\]]+$/g, "")
      .trim();
  }

  /**
   * Open whatever a field is hidden behind, and go to it.
   *
   * A message nobody can see is a message nobody acts on, and this form
   * folds away most of itself: sections collapse and instances sit behind
   * tabs.
   *
   * @private
   * @param {HTMLElement} column
   * @returns {void}
   */
  #reveal(column) {
    let node = column;
    while (node && node !== this.#container) {
      if (node.classList?.contains("tab-pane")) {
        const block = node.closest('[data-role$="-list"]');
        if (block) {
          this.#show(block, node.dataset.role, node.dataset.instance);
        }
      }
      if (
        node.dataset?.role === "section-body" &&
        node.classList.contains("collapse") &&
        !node.classList.contains("show")
      ) {
        this.#container
          .querySelector(`[data-role="section-toggle"][data-section="${node.id}"]`)
          ?.click();
      }
      node = node.parentElement;
    }
    column.scrollIntoView?.({ block: "center", behavior: "smooth" });
  }

  /**
   * @private
   * @returns {void}
   */
  #clearErrors() {
    this.#container.querySelectorAll("[data-error-for]").forEach((slot) => {
      slot.textContent = "";
      slot.classList.add("d-none");
    });
    this.#container
      .querySelectorAll(".is-invalid")
      .forEach((input) => input.classList.remove("is-invalid"));
    this.#container.querySelector('[data-role="messages"]')?.replaceChildren();
  }

  /**
   * @private
   * @returns {HTMLElement}
   */
  #messages() {
    const messages = document.createElement("div");
    messages.dataset.role = "messages";
    return messages;
  }

  /**
   * Say something that is not about one field in particular.
   *
   * Through the toast the rest of GOATS speaks through: it floats over the
   * page, so an answer to a button at the foot of the form is not left where
   * the form has to be scrolled back to read it. What a message is about is
   * still in the form -- each error sits under the field that raised it.
   *
   * @private
   * @param {string} text
   * @param {string} variant
   * @param {string} [label]
   * @returns {void}
   */
  #announce(text, variant, label = "Blanco") {
    if (typeof window !== "undefined" && window.toast) {
      window.toast.show({
        label,
        message: text,
        color: variant,
        // What went wrong waits to be read; what went right need not.
        autohide: variant !== "danger",
      });
      return;
    }
    // Nothing floating to say it through: say it where the form ends.
    let slot = this.#container.querySelector('[data-role="messages"]');
    if (!slot) {
      slot = this.#messages();
      this.#container.append(slot);
    }
    const alert = document.createElement("div");
    alert.className = `alert alert-${variant} mt-3`;
    alert.textContent = text;
    slot.replaceChildren(alert);
  }
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    const container = document.getElementById("blancoContainer");
    if (container) {
      new BlancoObservationForm(container).init();
    }
  });
}

if (typeof module !== "undefined") {
  module.exports = { BlancoObservationForm };
}

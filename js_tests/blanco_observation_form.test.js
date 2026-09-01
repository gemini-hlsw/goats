const { JSDOM } = require("jsdom");
const { js_dir } = require("./testConfig.js");
const fs = require("fs");
const path = require("path");

const field = (name, overrides = {}) => ({
  name,
  type: "text",
  label: name,
  help_text: "",
  required: false,
  hidden: false,
  initial: "",
  width: 6,
  ...overrides,
});

/** What the API serves: the Details section, open. */
const STRUCTURE = {
  sections: [
    {
      title: "Details",
      open: true,
      fields: [
        field("name", { required: true }),
        field("proposal", {
          type: "choice",
          choices: [{ value: "1", label: "Test (1)" }],
        }),
        field("ipp_value", { type: "float", initial: 1.05 }),
      ],
    },
  ],
};

function buildWindow() {
  const dom = new JSDOM(
    '<!DOCTYPE html><body><div id="blancoContainer" data-target-id="7"></div></body>',
    { runScripts: "dangerously", url: "https://goats.test/" },
  );
  ["blanco/field.js", "blanco/observation_form.js"].forEach((file) => {
    const script = dom.window.document.createElement("script");
    script.textContent = fs.readFileSync(path.join(js_dir, file), "utf8");
    dom.window.document.head.appendChild(script);
  });
  return dom.window;
}

/** Render the form against a stubbed API. */
async function render(window, { structure = STRUCTURE, response } = {}) {
  const calls = [];
  window.fetch = (url, options = {}) => {
    calls.push({ url, options });
    return Promise.resolve(response ?? { ok: true, json: async () => structure });
  };
  const BlancoObservationForm = window.eval("BlancoObservationForm");
  const form = new BlancoObservationForm(
    window.document.getElementById("blancoContainer"),
  );
  await form.init();
  return { form, calls, container: window.document.getElementById("blancoContainer") };
}

test("the form is drawn from what the API describes", async () => {
  const window = buildWindow();
  const { container, calls } = await render(window);

  expect(calls[0].url).toBe("/api/blanco/observations/?target_id=7");
  expect(container.querySelector("#id_name")).not.toBeNull();
  expect(container.querySelector("#id_proposal").tagName).toBe("SELECT");
  expect(container.querySelector("#id_ipp_value").value).toBe("1.05");
});

test("a section is the accordion the GPP form uses", async () => {
  const window = buildWindow();
  const { container } = await render(window);

  const header = container.querySelector('[data-role="section"]');
  const toggle = header.querySelector('[data-role="section-toggle"]');
  const body = container.querySelector("#section-details");

  expect(header.className).toBe(
    "d-flex align-items-center justify-content-between mt-4 mb-0",
  );
  expect(header.querySelector("h5").textContent).toBe("Details");
  expect(header.querySelector("h5").className).toBe("mb-0");
  expect(toggle.className).toBe("btn p-0");
  expect(toggle.getAttribute("data-bs-toggle")).toBe("collapse");
  expect(toggle.getAttribute("data-bs-target")).toBe("#section-details");
  // The chevron points up while the section is open, as GPP's does.
  expect(toggle.querySelector("i").className).toBe("fa-solid fa-chevron-up");
  expect(toggle.getAttribute("aria-expanded")).toBe("true");
  // The body carries the form's own grid, so the fields sit on it.
  expect(body.className).toBe("row g-3 mt-2 collapse show");
});

test("the chevron follows the section it belongs to", async () => {
  const window = buildWindow();
  const { container } = await render(window);
  const toggle = container.querySelector('[data-role="section-toggle"]');
  const body = container.querySelector("#section-details");

  body.dispatchEvent(new window.Event("hide.bs.collapse"));
  expect(toggle.querySelector("i").className).toBe("fa-solid fa-chevron-down");
  expect(toggle.getAttribute("aria-expanded")).toBe("false");

  body.dispatchEvent(new window.Event("show.bs.collapse"));
  expect(toggle.querySelector("i").className).toBe("fa-solid fa-chevron-up");
});

test("clicking the title opens the section, not just the chevron", async () => {
  const window = buildWindow();
  const { container } = await render(window);
  const toggle = container.querySelector('[data-role="section-toggle"]');
  let clicked = 0;
  toggle.addEventListener("click", () => (clicked += 1));

  container.querySelector('[data-role="section"] h5').click();

  expect(clicked).toBe(1);
});

test("every field is half a row or a whole one", async () => {
  const window = buildWindow();
  const { container } = await render(window, {
    structure: {
      sections: [
        {
          title: "Details",
          open: true,
          fields: [field("name"), field("note", { width: 12 })],
        },
      ],
    },
  });

  const widths = [...container.querySelectorAll("[data-field]")].map(
    (column) => column.className,
  );

  expect(widths).toEqual(["col-md-6", "col-12"]);
});

test("help is in its button and nowhere else", async () => {
  const window = buildWindow();
  const { container } = await render(window, {
    structure: {
      sections: [
        {
          title: "Details",
          open: true,
          fields: [
            field("ipp_value", {
              help_text: 'Read <a href="https://lco.global">this</a>.',
            }),
          ],
        },
      ],
    },
  });

  const column = container.querySelector("[data-field]");
  const button = column.querySelector('[data-role="help"]');

  // Nothing of the help is drawn in the form itself.
  expect(column.textContent).not.toContain("Read");
  expect(column.querySelector(".form-text")).toBeNull();
  // The words alone hover: a tooltip would show the markup.
  expect(button.title).toBe("Read this.");
  expect(button.getAttribute("aria-label")).toBe("Help for ipp_value");
  // GOATS ships the solid and brands sets only; fa-regular draws nothing.
  expect(button.querySelector("i").className).toBe("fa-solid fa-circle-question");
});

test("a field with nothing to explain gets no help button", async () => {
  const window = buildWindow();
  const { container } = await render(window);

  expect(container.querySelector('[data-role="help"]')).toBeNull();
});

test("help that is only whitespace is no help at all", async () => {
  const window = buildWindow();
  const { container } = await render(window, {
    structure: {
      sections: [
        { title: "Details", open: true, fields: [field("name", { help_text: " \n " })] },
      ],
    },
  });

  expect(container.querySelector('[data-role="help"]')).toBeNull();
});

test("a required field is marked, an optional one is not", async () => {
  const window = buildWindow();
  const { container } = await render(window);

  const required = container.querySelector("#id_name");
  const optional = container.querySelector("#id_ipp_value");

  // No asterisk: the control itself is what asks, while it has no answer.
  expect(container.querySelector('label[for="id_name"]').textContent).not.toContain("*");
  expect(required.className).toContain("border-danger");
  expect(optional.className).not.toContain("border-danger");
  // Colour alone says nothing to a screen reader.
  expect(required.getAttribute("aria-required")).toBe("true");
  expect(optional.hasAttribute("aria-required")).toBe(false);
});

test("a required control stops asking once it is answered", async () => {
  const window = buildWindow();
  const { container } = await render(window);
  const input = container.querySelector("#id_name");

  input.value = "my request";
  input.dispatchEvent(new window.Event("input"));
  expect(input.className).not.toContain("border-danger");

  input.value = "";
  input.dispatchEvent(new window.Event("input"));
  expect(input.className).toContain("border-danger");
});

test("a decimal input takes decimals", async () => {
  const window = buildWindow();
  const { container } = await render(window);

  const input = container.querySelector("#id_ipp_value");

  expect(input.type).toBe("number");
  expect(input.step).toBe("any");
});

test("what is collected uses the names the Django form expects", async () => {
  const window = buildWindow();
  const { form, container } = await render(window);
  container.querySelector("#id_name").value = "my request";

  const fields = form.collect();

  expect(fields.name).toBe("my request");
  expect(fields.ipp_value).toBe("1.05");
});

test("a form that cannot be loaded says so", async () => {
  const window = buildWindow();
  const { container } = await render(window, {
    response: { ok: false, status: 500, json: async () => ({}) },
  });

  expect(container.textContent).toContain("could not be loaded");
});

/** A form that repeats: two configurations, each of two exposures. */
const instrument = (id) =>
  field(`c_${id}_instrument_type`, {
    type: "choice",
    label: "Instrument",
    initial: "BLANCO_DECAM",
    choices: [
      { value: "BLANCO_DECAM", label: "DECam" },
      { value: "BLANCO_NEWFIRM", label: "NEWFIRM" },
    ],
  });

const exposures = (id) => ({
  title: "Exposures",
  open: true,
  repeat: "exposure",
  instances: [1, 2].map((n) => ({
    id: n,
    fields: [
      field(`c_${id}_ic_${n}_exposure_time`, { type: "float", required: true }),
      field(`c_${id}_ic_${n}_filter`, {
        type: "choice",
        choices: [
          { value: "r", label: "r" },
          { value: "JX", label: "JX" },
        ],
      }),
    ],
  })),
});

const REPEATED = {
  hidden: { facility: "BLANCO", observation_type: "IMAGING", target_id: "7" },
  instruments: {
    BLANCO_DECAM: {
      extra_detector_centering: { allowed: ["central_gap"], default: "central_gap" },
      filter: { allowed: ["r"] },
    },
    BLANCO_NEWFIRM: {
      extra_detector_centering: { allowed: ["det_1"], default: "det_1" },
      extra_dither_value: { min: 0, max: 1600 },
      filter: { allowed: ["JX"] },
      exposure_time: { max: 40 },
    },
  },
  sections: [
    {
      title: "Configuration",
      open: true,
      repeat: "configuration",
      instances: [1, 2].map((id) => ({
        id,
        fields: [
          instrument(id),
          field(`c_${id}_extra_detector_centering`, {
            type: "choice",
            choices: [
              { value: "central_gap", label: "Central gap" },
              { value: "det_1", label: "Det 1" },
            ],
          }),
          field(`c_${id}_extra_dither_value`, { type: "integer" }),
        ],
        sections: [exposures(id)],
      })),
    },
  ],
};

/** Render the repeated form, with an answer waiting for a POST. */
async function renderRepeated(window, answer, structure = REPEATED) {
  const posts = [];
  window.fetch = (url, options = {}) => {
    if (options.method === "POST") {
      posts.push({ url, options });
      return Promise.resolve({ ok: true, json: async () => answer });
    }
    return Promise.resolve({ ok: true, json: async () => structure });
  };
  const BlancoObservationForm = window.eval("BlancoObservationForm");
  const container = window.document.getElementById("blancoContainer");
  const form = new BlancoObservationForm(container);
  await form.init();
  return { form, container, posts };
}

/** Let the fetch and the promises hanging off it finish. */
const settled = () => new Promise((resolve) => setTimeout(resolve, 0));

const tabs = (container, role) =>
  [...container.querySelectorAll(`[data-role="${role}-tab"] .nav-link`)];

test("a nested section is not the accordion the section holding it is", async () => {
  const window = buildWindow();
  const { container } = await renderRepeated(window);

  const nested = container.querySelector('[data-role="section"][data-section="section-exposures"]');
  const heading = nested.querySelector("h6");

  // No chevron of its own: the weight is what tells the two apart.
  expect(heading.textContent).toBe("Exposures");
  expect(heading.className).toContain("text-uppercase");
  expect(nested.querySelector('[data-role="section-toggle"]')).toBeNull();
});

test("a repeated section draws one instance and adds the rest when asked", async () => {
  const window = buildWindow();
  const { container } = await renderRepeated(window);

  expect(tabs(container, "configuration")).toHaveLength(1);

  container.querySelector('[data-role="add-configuration"]').click();

  expect(tabs(container, "configuration")).toHaveLength(2);
  expect(container.querySelectorAll('[data-role="configuration"]')).toHaveLength(2);
});

test("a button that can do nothing looks spent", async () => {
  const window = buildWindow();
  const { container } = await renderRepeated(window);
  const add = container.querySelector('[data-role="add-configuration"]');
  const remove = container.querySelector('[data-role="remove-configuration"]');

  // Nothing to remove while there is one, nothing to add past the last.
  expect(remove.disabled).toBe(true);
  expect(remove.className).toContain("btn-outline-secondary");
  add.click();
  expect(remove.disabled).toBe(false);
  expect(remove.className).toContain("btn-outline-danger");
  expect(add.disabled).toBe(true);
  expect(add.className).toContain("btn-outline-secondary");
});

test("the last drawn is the one removed", async () => {
  const window = buildWindow();
  const { container } = await renderRepeated(window);
  container.querySelector('[data-role="add-configuration"]').click();

  container.querySelector('[data-role="remove-configuration"]').click();

  expect(tabs(container, "configuration").map((tab) => tab.textContent)).toEqual([
    "1 · DECam",
  ]);
});

/** The same form, with a proposal that only has time on one instrument. */
const PROPOSED = {
  ...REPEATED,
  proposals: { 1: ["BLANCO_DECAM"], 3: ["BLANCO_NEWFIRM"] },
  sections: [
    {
      title: "Details",
      open: true,
      fields: [
        field("name", { required: true }),
        field("proposal", {
          type: "choice",
          choices: [
            { value: "1", label: "DECam time (1)" },
            { value: "2", label: "Time on both (2)" },
            { value: "3", label: "NEWFIRM time (3)" },
          ],
        }),
      ],
    },
    ...REPEATED.sections,
  ],
};

/** Change the proposal to one of the others, as a reader would. */
function choose(window, container, proposal) {
  const select = container.querySelector('[data-field="proposal"] select');
  select.value = proposal;
  select.dispatchEvent(new window.Event("change"));
}

test("a configuration is kept to what the proposal has time on", async () => {
  const window = buildWindow();
  const { container } = await render(window, { structure: PROPOSED });
  const select = container.querySelector('[data-field="c_1_instrument_type"] select');
  const newfirm = [...select.options].find((o) => o.value === "BLANCO_NEWFIRM");

  // The proposal chosen has time on DECam and none on NEWFIRM.
  expect(newfirm.disabled).toBe(true);
  expect(select.value).toBe("BLANCO_DECAM");
});

test("a proposal named by no instrument is held to none", async () => {
  const window = buildWindow();
  const { container } = await render(window, { structure: PROPOSED });
  const proposal = container.querySelector('[data-field="proposal"] select');
  const select = container.querySelector('[data-field="c_1_instrument_type"] select');

  proposal.value = "2";
  proposal.dispatchEvent(new window.Event("change"));

  expect([...select.options].every((option) => !option.disabled)).toBe(true);
});

const drawn = (container, role) =>
  container.querySelectorAll(`[data-role="${role}"]`).length;

const valueOf = (container, name) =>
  container.querySelector(`[data-field="${name}"] input, [data-field="${name}"] select`)
    .value;

test("a proposal that cannot pay for the request starts it again", async () => {
  const window = buildWindow();
  const { container } = await render(window, { structure: PROPOSED });
  container.querySelector('[data-role="add-configuration"]').click();

  expect(drawn(container, "configuration")).toBe(2);

  // Chosen for DECam, and this proposal has time on NEWFIRM alone.
  choose(window, container, "3");

  // The one configuration a form is drawn with, on an instrument this
  // proposal can pay for.
  expect(drawn(container, "configuration")).toBe(1);
  expect(valueOf(container, "c_1_instrument_type")).toBe("BLANCO_NEWFIRM");
});

test("what a proposal was filled in with comes back with it", async () => {
  const window = buildWindow();
  const { container } = await render(window, { structure: PROPOSED });
  container.querySelector('[data-field="c_1_ic_1_exposure_time"] input').value = "45";
  container.querySelector('[data-role="add-configuration"]').click();

  choose(window, container, "3");
  choose(window, container, "1");

  expect(drawn(container, "configuration")).toBe(2);
  expect(valueOf(container, "c_1_instrument_type")).toBe("BLANCO_DECAM");
  expect(valueOf(container, "c_1_ic_1_exposure_time")).toBe("45");
});

test("a proposal that can pay for what is on show leaves it alone", async () => {
  const window = buildWindow();
  const { container } = await render(window, { structure: PROPOSED });
  container.querySelector('[data-field="c_1_ic_1_exposure_time"] input').value = "45";

  // Time on both, so what was filled in for DECam is still paid for.
  choose(window, container, "2");

  expect(valueOf(container, "c_1_ic_1_exposure_time")).toBe("45");
  expect(valueOf(container, "c_1_instrument_type")).toBe("BLANCO_DECAM");
});

test("the request is not what the proposal takes away", async () => {
  const window = buildWindow();
  const { container } = await render(window, { structure: PROPOSED });
  container.querySelector('[data-field="name"] input').value = "a request";

  choose(window, container, "3");

  expect(valueOf(container, "name")).toBe("a request");
  expect(valueOf(container, "proposal")).toBe("3");
});

test("what another proposal was filled in with is never sent", async () => {
  const window = buildWindow();
  const { container, posts } = await renderRepeated(window, { valid: true }, PROPOSED);
  container.querySelector('[data-field="c_1_ic_1_exposure_time"] input').value = "45";
  container.querySelector('[data-role="add-configuration"]').click();

  choose(window, container, "3");
  container.querySelector('[data-field="c_1_ic_1_exposure_time"] input').value = "20";
  container.querySelector('[data-role="validate"]').click();
  await settled();

  const sent = JSON.parse(posts[0].options.body).fields;

  // The one configuration this proposal pays for, and what it was filled in
  // with. What the other holds is held in memory, and never in the form.
  expect(sent.proposal).toBe("3");
  expect(sent.c_1_instrument_type).toBe("BLANCO_NEWFIRM");
  expect(sent.c_1_ic_1_exposure_time).toBe("20");
  expect(Object.keys(sent).filter((name) => name.startsWith("c_2_"))).toEqual([]);
});

test("a tab says what is inside it", async () => {
  const window = buildWindow();
  const { container } = await renderRepeated(window);
  const select = container.querySelector('[data-field="c_1_instrument_type"] select');

  expect(tabs(container, "configuration")[0].textContent).toBe("1 · DECam");
  expect(tabs(container, "exposure")[0].textContent).toBe("1 · r");

  select.value = "BLANCO_NEWFIRM";
  select.dispatchEvent(new window.Event("change"));

  expect(tabs(container, "configuration")[0].textContent).toBe("1 · NEWFIRM");
  // Narrowing took the filter DECam had, and the tab followed it.
  expect(tabs(container, "exposure")[0].textContent).toBe("1 · JX");
});

test("a parameter the instrument never declared does not apply to it", async () => {
  const window = buildWindow();
  const { container } = await renderRepeated(window);
  const dither = container.querySelector('[data-field="c_1_extra_dither_value"]');
  const select = container.querySelector('[data-field="c_1_instrument_type"] select');

  // DECam does not dither at all.
  expect(dither.className).toContain("d-none");

  select.value = "BLANCO_NEWFIRM";
  select.dispatchEvent(new window.Event("change"));

  expect(dither.className).not.toContain("d-none");
  expect(dither.querySelector("input").max).toBe("1600");
});

test("what an instrument does not take is not left chosen", async () => {
  const window = buildWindow();
  const { container } = await renderRepeated(window);
  const centering = container.querySelector(
    '[data-field="c_1_extra_detector_centering"] select',
  );
  const select = container.querySelector('[data-field="c_1_instrument_type"] select');

  expect(centering.value).toBe("central_gap");

  select.value = "BLANCO_NEWFIRM";
  select.dispatchEvent(new window.Event("change"));

  expect(centering.value).toBe("det_1");
  expect([...centering.options].find((o) => o.value === "central_gap").disabled).toBe(
    true,
  );
});

test("an exposure added later follows the instrument already chosen", async () => {
  const window = buildWindow();
  const { container } = await renderRepeated(window);
  const select = container.querySelector('[data-field="c_1_instrument_type"] select');
  select.value = "BLANCO_NEWFIRM";
  select.dispatchEvent(new window.Event("change"));

  container.querySelector('[data-role="add-exposure"]').click();

  const added = container.querySelector('[data-field="c_1_ic_2_exposure_time"] input');
  expect(added.max).toBe("40");
});

test("a parameter that does not apply is never sent", async () => {
  const window = buildWindow();
  const { form } = await renderRepeated(window);

  // DECam is chosen, so the dither is hidden.
  expect(Object.keys(form.collect())).not.toContain("c_1_extra_dither_value");
});

test("a required control asks on itself until it is answered", async () => {
  const window = buildWindow();
  const { container } = await renderRepeated(window);

  const time = container.querySelector('[data-field="c_1_ic_1_exposure_time"] input');

  expect(time.className).toContain("border-danger");
});

test("what was filled in is checked before anything is submitted", async () => {
  const window = buildWindow();
  window.document.body.dataset.csrfToken = "a-token";
  const { container, posts } = await renderRepeated(window, {
    valid: true,
    message: "This observation is valid with a duration of 300 seconds.",
  });

  container.querySelector('[data-role="validate"]').click();
  await settled();

  expect(posts[0].url).toBe("/api/blanco/observations/");
  expect(posts[0].options.headers["X-CSRFToken"]).toBe("a-token");
  expect(JSON.parse(posts[0].options.body).fields.c_1_instrument_type).toBe(
    "BLANCO_DECAM",
  );
  expect(container.textContent).toContain("duration of 300 seconds");
});

test("an error is put under the field it was raised on", async () => {
  const window = buildWindow();
  const { container } = await renderRepeated(window, {
    valid: false,
    errors: { c_1_ic_1_exposure_time: ["This field is required."] },
  });

  container.querySelector('[data-role="validate"]').click();
  await settled();

  const slot = container.querySelector('[data-error-for="c_1_ic_1_exposure_time"]');
  expect(slot.textContent).toBe("This field is required.");
  expect(slot.className).not.toContain("d-none");
  expect(
    container.querySelector('[data-field="c_1_ic_1_exposure_time"] input').className,
  ).toContain("is-invalid");
});

test("an error on a field behind a tab brings that tab to the front", async () => {
  const window = buildWindow();
  const { container } = await renderRepeated(window, {
    valid: false,
    errors: { c_1_ic_2_exposure_time: ["This field is required."] },
  });
  container.querySelector('[data-role="add-exposure"]').click();
  // Back to the first, so the error is on one nobody is looking at.
  tabs(container, "exposure")[0].click();

  container.querySelector('[data-role="validate"]').click();
  await settled();

  expect(tabs(container, "exposure")[1].className).toContain("active");
});

test("what the portal refused is listed where it can be read", async () => {
  const window = buildWindow();
  const { container } = await renderRepeated(window, {
    valid: false,
    errors: {
      __all__: [
        "Configuration 1, exposure 1, exposure time: Ensure this is at most 40.",
        "Window 1, end: The window ends before it starts.",
      ],
      c_1_ic_1_exposure_time: ["This field is required."],
    },
  });

  container.querySelector('[data-role="validate"]').click();
  await settled();

  const listed = [
    ...container.querySelectorAll('[data-role="refusal"] li'),
  ].map((item) => item.textContent);

  expect(listed).toEqual([
    "Configuration 1, exposure 1, exposure time: Ensure this is at most 40.",
    "Window 1, end: The window ends before it starts.",
  ]);
  // What was raised on a field is still said under that field.
  expect(
    container.querySelector('[data-error-for="c_1_ic_1_exposure_time"]').textContent,
  ).toBe("This field is required.");
});

test("the portal's own machinery is not read out loud", async () => {
  const window = buildWindow();
  const BlancoObservationForm = window.eval("BlancoObservationForm");

  expect(
    BlancoObservationForm.plainly("non_field_errors: No configurations."),
  ).toBe("No configurations.");
  expect(BlancoObservationForm.plainly("windows: End before start.")).toBe(
    "windows: End before start.",
  );
});

test("a form found sound is handed to the toolkit's own view", async () => {
  const window = buildWindow();
  window.document.body.dataset.csrfToken = "a-token";
  const posted = [];
  window.HTMLFormElement.prototype.submit = function () {
    posted.push(this);
  };
  const { container } = await renderRepeated(window, { valid: true, message: "" });

  container.querySelector('[data-role="submit"]').click();
  await settled();

  expect(posted).toHaveLength(1);
  const sent = Object.fromEntries(
    [...posted[0].querySelectorAll("input")].map((input) => [input.name, input.value]),
  );
  expect(posted[0].method).toBe("post");
  expect(sent.facility).toBe("BLANCO");
  expect(sent.observation_type).toBe("IMAGING");
  expect(sent.csrfmiddlewaretoken).toBe("a-token");
  expect(sent.c_1_instrument_type).toBe("BLANCO_DECAM");
});

test("nothing is submitted while the form is not sound", async () => {
  const window = buildWindow();
  const posted = [];
  window.HTMLFormElement.prototype.submit = function () {
    posted.push(this);
  };
  const { container } = await renderRepeated(window, {
    valid: false,
    errors: { name: ["This field is required."] },
  });

  container.querySelector('[data-role="submit"]').click();
  await settled();

  expect(posted).toHaveLength(0);
});

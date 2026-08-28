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

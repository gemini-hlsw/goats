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

/** A window with the field builder loaded, and Bootstrap if asked for. */
function buildWindow({ popovers = false } = {}) {
  const dom = new JSDOM("<!DOCTYPE html><body></body>", {
    runScripts: "dangerously",
  });
  const made = [];
  if (popovers) {
    dom.window.bootstrap = {
      Popover: class {
        constructor(element, options) {
          made.push({ element, options });
        }
        static getInstance() {
          return null;
        }
      },
    };
  }
  const script = dom.window.document.createElement("script");
  script.textContent = fs.readFileSync(path.join(js_dir, "blanco/field.js"), "utf8");
  dom.window.document.head.appendChild(script);
  return { window: dom.window, BlancoField: dom.window.eval("BlancoField"), made };
}

test("a choice arrives as a select of what the form accepts", () => {
  const { BlancoField } = buildWindow();

  const column = BlancoField.build(
    field("filter", {
      type: "choice",
      initial: "JX",
      choices: [
        { value: "r", label: "r" },
        { value: "JX", label: "JX" },
      ],
    }),
  );
  const select = column.querySelector("select");

  expect(select.className).toBe("form-select");
  expect([...select.options].map((option) => option.value)).toEqual(["r", "JX"]);
  expect(select.value).toBe("JX");
});

test("a boolean arrives as a checkbox, labelled once", () => {
  const { BlancoField } = buildWindow();

  const column = BlancoField.build(
    field("extra_dither_sequence_random_offset", {
      type: "boolean",
      label: "Dither Sequence Random Offset",
      initial: true,
    }),
  );

  const input = column.querySelector("input");
  expect(input.type).toBe("checkbox");
  expect(input.checked).toBe(true);
  // The check carries its own label; a second one above it would repeat it.
  expect(column.querySelectorAll("label")).toHaveLength(1);
});

test("a number keeps the bounds its instrument sets", () => {
  const { BlancoField } = buildWindow();

  const column = BlancoField.build(
    field("extra_dither_value", { type: "integer", min: 0, max: 1600 }),
  );
  const input = column.querySelector("input");

  expect(input.type).toBe("number");
  expect(input.min).toBe("0");
  expect(input.max).toBe("1600");
});

test("what a field is measured in sits beside it", () => {
  const { BlancoField } = buildWindow();

  const column = BlancoField.build(
    field("exposure_time", { type: "float", unit: "s" }),
  );

  expect(column.querySelector(".input-group")).not.toBeNull();
  expect(column.querySelector('[data-role="unit"]').textContent).toBe("s");
  // The unit is beside the control, so nothing is left inside it.
  expect(column.querySelector("input").placeholder).toBe("");
});

test("a split datetime is read as the two halves the form is built from", () => {
  const { BlancoField } = buildWindow();
  const column = BlancoField.build(field("start", { type: "datetime" }));
  const input = column.querySelector("input");
  input.value = "2026-09-01T20:00";

  expect(input.type).toBe("datetime-local");
  expect(BlancoField.read(input)).toEqual({
    start_0: "2026-09-01",
    start_1: "20:00",
  });
});

test("a checkbox is read as what it is, not as what it says", () => {
  const { BlancoField } = buildWindow();
  const column = BlancoField.build(field("agreed", { type: "boolean" }));
  const input = column.querySelector("input");

  expect(BlancoField.read(input)).toEqual({ agreed: false });
  input.checked = true;
  expect(BlancoField.read(input)).toEqual({ agreed: true });
});

test("help keeps the link the toolkit wrote into it", () => {
  const { BlancoField, made } = buildWindow({ popovers: true });

  const column = BlancoField.build(
    field("end", {
      help_text: 'Try the <a href="https://lco.global/visibility/">calculator</a>.',
    }),
  );

  expect(column.querySelector('[data-role="help"]').title).toBe("");
  expect(made).toHaveLength(1);
  expect(made[0].options.html).toBe(true);
  // A link out of GOATS opens beside it, whatever the toolkit wrote.
  expect(made[0].options.content).toContain('target="_blank"');
  expect(made[0].options.content).toContain('rel="noopener"');
});

test("with nothing to open a popover with, the words alone hover", () => {
  const { BlancoField } = buildWindow();

  const column = BlancoField.build(
    field("end", { help_text: 'Try the <a href="https://lco.global/">calculator</a>.' }),
  );

  expect(column.querySelector('[data-role="help"]').title).toBe(
    "Try the calculator.",
  );
});

test("a value written for a control is looked at again", () => {
  const { BlancoField } = buildWindow();
  const column = BlancoField.build(
    field("filter", {
      type: "choice",
      required: true,
      choices: [{ value: "", label: "---" }],
    }),
  );
  const select = column.querySelector("select");

  // Narrowing writes a value without anybody typing it, and raises nothing.
  expect(select.className).toContain("border-danger");
  select.options[0].value = "JX";
  select.value = "JX";
  BlancoField.recheck(select);

  expect(select.className).not.toContain("border-danger");
});

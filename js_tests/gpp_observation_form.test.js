const { JSDOM } = require("jsdom");
const { js_dir } = require("./testConfig.js");
const fs = require("fs");
const path = require("path");

/** The scripts the observation form template loads, in its order. */
const SCRIPTS = [
  "utils.js",
  "gpp/lookups.js",
  "gpp/formatters.js",
  "gpp/fields.js",
  "gpp/pos_angle_editor.js",
  "gpp/brightnesses_editor.js",
  "gpp/source_profile_editor.js",
  "gpp/science_band_editor.js",
  "gpp/elevation_range_editor.js",
  "gpp/exposure_mode_editor.js",
  "gpp/scheduling_windows_editor.js",
  "gpp/finder_chart_editor.js",
  "gpp/offset_variant_editor.js",
  "gpp/observation_form.js",
  "gpp/gpp.js",
];

/** What the enums endpoint serves for the scheduling choices. */
const ENUMS = {
  priority: ["LOW", "MEDIUM", "HIGH"],
  tooActivation: ["NONE", "RAPID", "INTERRUPTING"],
  schedulingMode: ["UNCONSTRAINED", "NO_SPLITTING", "UNINTERRUPTIBLE"],
  imageQuality: ["POINT_ONE"],
};

function buildWindow() {
  const dom = new JSDOM('<!DOCTYPE html><body><div id="form"></div></body>', {
    runScripts: "dangerously",
  });
  SCRIPTS.forEach((file) => {
    const script = dom.window.document.createElement("script");
    script.textContent = fs.readFileSync(path.join(js_dir, file), "utf8");
    dom.window.document.head.appendChild(script);
  });
  dom.window.console.warn = () => {};
  dom.window.console.debug = () => {};
  return dom.window;
}

async function enumFieldOptions(window) {
  const GPPModel = window.eval("GPPModel");
  const model = new GPPModel({ api: { get: async () => ENUMS } });
  await model.fetchEnums();
  return model.enumFieldOptions();
}

async function renderForm(window, schedulingConstraints, { readOnly = false } = {}) {
  const ObservationForm = window.eval("ObservationForm");
  const form = new ObservationForm(window.document.getElementById("form"), {
    observation: { priority: "MEDIUM", schedulingConstraints },
    readOnly,
    fieldOptions: await enumFieldOptions(window),
  });
  return {
    form,
    priority: window.document.getElementById("prioritySelect"),
    activation: window.document.getElementById("tooActivationSelect"),
    mode: window.document.getElementById("schedulingModeSelect"),
  };
}

function choose(select, value) {
  select.value = value;
  select.dispatchEvent(new select.ownerDocument.defaultView.Event("change"));
}

test("every served enum is offered, labelled by Lookups or its own name", async () => {
  const options = await enumFieldOptions(buildWindow());

  expect(options.schedulingMode).toEqual([
    { value: "UNCONSTRAINED", labelText: "Unconstrained" },
    { value: "NO_SPLITTING", labelText: "No Splitting" },
    { value: "UNINTERRUPTIBLE", labelText: "Uninterruptible" },
  ]);
  expect(options.imageQuality).toEqual([
    { value: "POINT_ONE", labelText: "< 0.10" },
  ]);
});

test("the scheduling selects offer what GPP serves", async () => {
  const { priority, activation, mode } = await renderForm(buildWindow(), {
    tooActivation: "NONE",
    schedulingMode: "NO_SPLITTING",
  });

  expect([...priority.options].map((o) => o.value)).toEqual(ENUMS.priority);
  expect(priority.value).toBe("MEDIUM");
  expect(activation.value).toBe("NONE");
  expect(mode.value).toBe("NO_SPLITTING");
  expect(mode.disabled).toBe(false);
});

test.each(["RAPID", "INTERRUPTING"])(
  "a %s activation fixes the mode at UNINTERRUPTIBLE",
  async (value) => {
    const { activation, mode } = await renderForm(buildWindow(), {
      tooActivation: "NONE",
      schedulingMode: "UNCONSTRAINED",
    });

    choose(activation, value);

    expect(mode.value).toBe("UNINTERRUPTIBLE");
    expect(mode.disabled).toBe(true);
  },
);

test("lowering the activation leaves the mode alone but editable", async () => {
  const { activation, mode } = await renderForm(buildWindow(), {
    tooActivation: "RAPID",
    schedulingMode: "UNINTERRUPTIBLE",
  });
  expect(mode.disabled).toBe(true);

  choose(activation, "NONE");

  expect(mode.value).toBe("UNINTERRUPTIBLE");
  expect(mode.disabled).toBe(false);
});

test("the timing windows are read from the scheduling constraints", async () => {
  const window = buildWindow();
  window.structuredClone = (value) => JSON.parse(JSON.stringify(value));
  const timingWindow = {
    inclusion: "INCLUDE",
    startUtc: "2026-10-15 00:00:00",
    end: { atUtc: "2026-10-16 00:00:00" },
  };
  const { form } = await renderForm(window, {
    tooActivation: "NONE",
    schedulingMode: "UNCONSTRAINED",
    timingWindows: [timingWindow],
  });

  expect(JSON.parse(form.getData().get("timingWindows"))).toEqual([timingWindow]);
});

/** The enum options for a program, as the model hands them to the form. */
async function programFieldOptions(window, program) {
  const GPPModel = window.eval("GPPModel");
  const model = new GPPModel({
    api: {
      get: async (url) => (url.includes("enums") ? ENUMS : { matches: [program] }),
    },
  });
  await model.fetchEnums();
  await model.fetchPrograms();
  model.getProgram(program.id);
  return model.enumFieldOptions();
}

test.each([
  ["NONE", ["NONE"]],
  ["RAPID", ["NONE", "RAPID"]],
  ["INTERRUPTING", ["NONE", "RAPID", "INTERRUPTING"]],
  [null, ["NONE", "RAPID", "INTERRUPTING"]],
])("a %p ceiling lets pick %p", async (ceiling, selectable) => {
  const { tooActivation } = await programFieldOptions(buildWindow(), {
    id: "p-1",
    tooActivationCeiling: ceiling,
  });

  expect(tooActivation.map((o) => o.value)).toEqual(ENUMS.tooActivation);
  expect(tooActivation.filter((o) => !o.disabled).map((o) => o.value)).toEqual(
    selectable,
  );
});

test.each([
  ["RAPID", "RAPID"],
  ["INTERRUPTING", "INTERRUPTING"],
  [null, "NONE"],
])("a new observation under a %p ceiling starts at %p", async (ceiling, expected) => {
  const GPPModel = buildWindow().eval("GPPModel");
  const model = new GPPModel({
    api: { get: async () => ({ matches: [{ id: "p-1", tooActivationCeiling: ceiling }] }) },
  });
  await model.fetchPrograms();
  model.getProgram("p-1");

  const { observation } = model.buildConfigurationObservation(
    { configuration: { observingMode: {} } },
    {},
  );

  expect(observation.schedulingConstraints.tooActivation).toBe(expected);
});

test("the form shows the activations above the ceiling disabled", async () => {
  const window = buildWindow();
  const ObservationForm = window.eval("ObservationForm");
  new ObservationForm(window.document.getElementById("form"), {
    observation: { schedulingConstraints: { tooActivation: "NONE" } },
    fieldOptions: await programFieldOptions(window, {
      id: "p-1",
      tooActivationCeiling: "RAPID",
    }),
  });

  const select = window.document.getElementById("tooActivationSelect");
  expect([...select.options].map((o) => [o.value, o.disabled])).toEqual([
    ["NONE", false],
    ["RAPID", false],
    ["INTERRUPTING", true],
  ]);
});

test("a read-only form keeps the mode disabled", async () => {
  const { activation, mode } = await renderForm(
    buildWindow(),
    { tooActivation: "NONE", schedulingMode: "UNCONSTRAINED" },
    { readOnly: true },
  );

  choose(activation, "NONE");

  expect(mode.disabled).toBe(true);
});

/** An approved configuration request whose target is `target`. */
function configurationRequest(id, target) {
  return { id, configuration: { target, observingMode: {} } };
}

/** A region whose arcs are of the given types. */
function region(raType, decType) {
  return {
    region: {
      rightAscensionArc: { type: raType, start: null, end: null },
      declinationArc: { type: decType, start: null, end: null },
    },
  };
}

test("only the configurations approved for a region are offered for a ToO", async () => {
  const GPPModel = buildWindow().eval("GPPModel");
  const model = new GPPModel({
    api: {
      get: async () => ({
        matches: [
          configurationRequest("full", region("FULL", "FULL")),
          configurationRequest("range", region("PARTIAL", "FULL")),
          configurationRequest("empty", region("EMPTY", "FULL")),
          configurationRequest("fixed", {
            coordinates: { ra: { degrees: 10 }, dec: { degrees: -20 } },
            region: null,
          }),
          configurationRequest("none", null),
        ],
      }),
    },
  });

  await model.fetchTooConfigurations("p-1");

  expect(model.tooConfigurationsList.map((c) => c.id)).toEqual(["full", "range"]);
  expect(model.getTooConfiguration("fixed")).toBeUndefined();
});

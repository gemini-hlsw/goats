const { JSDOM } = require("jsdom");
const { js_dir } = require("./testConfig.js");
const fs = require("fs");
const path = require("path");

/** The scripts the observation form template loads, in its order. */
const SCRIPTS = [
  "../tom-select/tom-select.base.js",
  "utils.js",
  "gpp/lookups.js",
  "gpp/formatters.js",
  "gpp/fields.js",
  "gpp/pos_angle_editor.js",
  "gpp/brightnesses_editor.js",
  "gpp/source_profile_editor.js",
  "gpp/program_observations_panel.js",
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

/** An approved GMOS North long slit configuration over a partial region. */
function longSlitConfiguration() {
  const configuration = configurationRequest("cr-1", region("FULL", "PARTIAL"));
  configuration.configuration.observingMode = {
    instrument: "GMOS_NORTH",
    mode: "GMOS_NORTH_LONG_SLIT",
    gmosNorthLongSlit: { grating: "R831_G5302" },
  };
  configuration.configuration.conditions = {
    imageQuality: "POINT_EIGHT",
    cloudExtinction: "POINT_THREE",
    skyBackground: "DARK",
    waterVapor: "VERY_DRY",
  };
  return configuration;
}

test("an imaging configuration's setup names its filters short", () => {
  const ProgramObservationsPanel = buildWindow().eval("ProgramObservationsPanel");
  const configuration = configurationRequest("cr-4", null);
  configuration.configuration.observingMode = {
    instrument: "GMOS_SOUTH",
    mode: "GMOS_SOUTH_IMAGING",
    gmosSouthImaging: { filters: ["G_PRIME", "R_PRIME_RG610"] },
  };

  expect(ProgramObservationsPanel.configurationSetup(configuration)).toBe(
    "GMOS-S Imaging g,r+RG610",
  );
});

test("a configuration's setup is short, as in Explore", () => {
  const ProgramObservationsPanel = buildWindow().eval("ProgramObservationsPanel");

  expect(ProgramObservationsPanel.configurationSetup(longSlitConfiguration())).toBe(
    "GMOS-N LongSlit R831",
  );
});

test("a configuration is labelled as observations are: its ID, then its target", () => {
  const ProgramObservationsPanel = buildWindow().eval("ProgramObservationsPanel");
  const label = (targets) =>
    ProgramObservationsPanel.configurationLabel(longSlitConfiguration(), targets);

  expect(label(["Boom5"])).toBe("cr-1 - Boom5");
  expect(label(["Boom3", "AT2026xyz"])).toBe("cr-1 - Multiple");
  expect(label([])).toBe("cr-1");
});

test("a configuration's targets are those of the observations asking for it", async () => {
  const GPPModel = buildWindow().eval("GPPModel");
  const observation = (id, configurationRequestIds, ...names) => ({
    id,
    configurationRequests: configurationRequestIds.map((crId) => ({ id: crId })),
    targetEnvironment: { asterism: names.map((name) => ({ name })) },
  });
  const model = new GPPModel({
    api: {
      get: async (url) =>
        url.includes("configuration-requests")
          ? {
              matches: ["one", "many", "none"].map((id) => ({
                ...configurationRequest(id, region("FULL", "FULL")),
                // Missing the ToO observation, as GPP leaves it out.
                applicableObservations: [],
              })),
            }
          : {
              matches: {
                results: [
                  observation("o-1", ["one", "many"], "Boom5"),
                  observation("o-2", ["one"], "Boom5"),
                  observation("o-3", ["many"], "SN-ToO"),
                  {
                    ...observation("o-4", ["one"], "Feige 34"),
                    calibrationRole: "SPECTROPHOTOMETRIC",
                  },
                  observation("o-5", ["withdrawn"], "Gone"),
                ],
              },
            },
    },
  });

  await model.fetchObservations("p-1");
  await model.fetchTooConfigurations("p-1");

  expect(Object.fromEntries(model.tooConfigurationTargets)).toEqual({
    one: ["Boom5"],
    many: ["Boom5", "SN-ToO"],
    none: [],
  });
});

test("a configuration is summed up in Explore's order: region, then conditions", () => {
  const ProgramObservationsPanel = buildWindow().eval("ProgramObservationsPanel");

  const summary = ProgramObservationsPanel.configurationSummary(longSlitConfiguration());
  expect(summary).toEqual([
    ["RA", "Full"],
    ["Dec", "Partial"],
    ["IQ", "< 0.80 arcsec"],
    ["CC", "< 0.30 mag"],
    ["SB", "Dark"],
    ["WV", "Very Dry"],
  ]);
});

test("a partial arc is summed up as its range", () => {
  const ProgramObservationsPanel = buildWindow().eval("ProgramObservationsPanel");
  const configuration = configurationRequest("cr-3", region("FULL", "PARTIAL"));
  configuration.configuration.target.region.declinationArc = {
    type: "PARTIAL",
    start: { dms: "-30:00:00.000000", degrees: 330 },
    end: { dms: "+10:30:15.250000", degrees: 10.504 },
  };

  const summary = ProgramObservationsPanel.configurationSummary(configuration);
  expect(summary.slice(0, 2)).toEqual([
    ["RA", "Full"],
    ["Dec", "-30:00:00 - +10:30:15.25"],
  ]);
});

/** A panel whose ToO select lists the long slit configuration. */
function panelWithConfiguration() {
  const window = buildWindow();
  const ProgramObservationsPanel = window.eval("ProgramObservationsPanel");
  const panel = new ProgramObservationsPanel(window.document.getElementById("form"));
  panel.updateTooConfigurations([longSlitConfiguration()]);
  const document = window.document;
  return {
    window,
    panel,
    tomSelect: document.getElementById("tooObservationSelect").tomselect,
    normalSelect: document.getElementById("normalObservationSelect"),
  };
}

/** The texts of the terms and details an option shows, in order. */
function detailsTexts(option) {
  const list = option.querySelector("dl");
  return Array.from(list.querySelectorAll("dt, dd"), (cell) => cell.textContent);
}

const LONG_SLIT_DETAILS = [
  "RA",
  "Full",
  "Dec",
  "Partial",
  "IQ",
  "< 0.80 arcsec",
  "CC",
  "< 0.30 mag",
  "SB",
  "Dark",
  "WV",
  "Very Dry",
];


test("the panel's three selects are drawn by Tom Select, following their native selects", () => {
  const { window, panel } = panelWithConfiguration();
  const tomSelectOf = (id) => window.document.getElementById(id).tomselect;
  const programs = tomSelectOf("programSelect");
  const observations = tomSelectOf("normalObservationSelect");

  panel.updatePrograms([{ id: "p-1", name: "Rubin alerts" }]);
  panel.updateNormalObservations([
    { id: "o-1", title: "SN 2026a" },
    { id: "o-2", title: "Boom3", isToo: true },
  ]);

  expect(programs.options["p-1"].text).toBe("p-1 - Rubin alerts");
  expect(programs.isDisabled).toBe(false);
  // The observations keep their groups.
  expect(observations.options["o-2"].optgroup).toBeDefined();
  expect(tomSelectOf("tooObservationSelect").getOption("cr-1", true).classList).toContain(
    "too-configuration-option",
  );

  panel.clearNormalSelect();
  panel.toggleNormalSelect(true);
  expect(Object.keys(observations.options)).toEqual([]);
  expect(observations.isDisabled).toBe(true);
});

test("the ToO select lists one line per configuration, with no search", () => {
  const { tomSelect } = panelWithConfiguration();

  expect(tomSelect.options["cr-1"].text).toBe("cr-1");
  expect(tomSelect.control_input.readOnly).toBe(true);
  expect(tomSelect.isDisabled).toBe(false);
});

test("each ToO option shows its configuration's details under its label", () => {
  const { tomSelect } = panelWithConfiguration();
  tomSelect.refreshOptions(false);
  const option = tomSelect.getOption("cr-1");

  expect(option.firstChild.textContent).toBe("cr-1");
  // Its setup first, then the rest.
  expect(option.querySelector(".too-configuration-setup").textContent).toBe(
    "GMOS-N LongSlit R831",
  );
  expect(detailsTexts(option)).toEqual(LONG_SLIT_DETAILS);
  // One div around each term and its detail, as a description list allows.
  const list = option.querySelector("dl");
  for (const group of list.children) {
    expect(Array.from(group.children, (cell) => cell.tagName)).toEqual(["DT", "DD"]);
  }
});

test("hovering a ToO option highlights it", () => {
  const { window, tomSelect } = panelWithConfiguration();
  tomSelect.refreshOptions(false);
  const option = tomSelect.getOption("cr-1");

  option.dispatchEvent(new window.MouseEvent("mouseover", { bubbles: true }));

  expect(option.classList).toContain("active");
});

test("a GMOS MOS or IFU configuration's setup names its focal plane, as in Explore", () => {
  const ProgramObservationsPanel = buildWindow().eval("ProgramObservationsPanel");
  const configuration = configurationRequest("cr-5", null);
  configuration.configuration.observingMode = {
    instrument: "GMOS_NORTH",
    mode: "GMOS_NORTH_IFU",
  };

  expect(ProgramObservationsPanel.configurationSetup(configuration)).toBe("GMOS-N IFU");
});

test("picking a ToO configuration reports it", () => {
  const { panel, tomSelect } = panelWithConfiguration();
  const picked = [];
  panel.onTooSelect((id) => picked.push(id));

  tomSelect.addItem("cr-1");

  expect(picked).toEqual(["cr-1"]);
});

test("picking an observation or clearing the ToO select empties its choice", () => {
  const { window, panel, tomSelect, normalSelect } = panelWithConfiguration();
  panel.onTooSelect(() => {});
  panel.onNormalSelect(() => {});

  tomSelect.addItem("cr-1");
  normalSelect.dispatchEvent(new window.Event("change"));
  expect(tomSelect.getValue()).toBe("");

  tomSelect.addItem("cr-1");
  panel.clearTooSelect();
  panel.toggleTooSelect(true);
  expect(Object.keys(tomSelect.options)).toEqual([]);
  expect(tomSelect.isDisabled).toBe(true);
});

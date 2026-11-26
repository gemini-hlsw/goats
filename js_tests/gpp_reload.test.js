const { JSDOM } = require("jsdom");
const { js_dir } = require("./testConfig.js");
const fs = require("fs");
const path = require("path");

function buildWindow() {
  const dom = new JSDOM("<!DOCTYPE html><body></body>", {
    runScripts: "dangerously",
  });
  ["utils.js", "gpp/lookups.js", "gpp/gpp.js"].forEach((file) => {
    const script = dom.window.document.createElement("script");
    script.textContent = fs.readFileSync(path.join(js_dir, file), "utf8");
    dom.window.document.head.appendChild(script);
  });
  return dom.window;
}

/** What the server answers, as far as the lists are concerned. */
const answer = (status) => ({ status, summary: "", messages: [] });

/** Send a request, answer it, and tell what was done with the lists. */
async function send({
  status,
  data,
  selection = { normal: "o-3a7", too: "", disabled: [false, false, true] },
  observation = { id: "o-3a7" },
  answered = true,
  event = "updateObservation",
}) {
  const window = buildWindow();
  const GPPController = window.eval("GPPController");
  const formData = new window.FormData();
  const calls = { refreshed: 0, renders: [] };
  const callbacks = {};
  const view = {
    bindCallback: (name, handler) => (callbacks[name] = handler),
    render: (command, parameter) => {
      calls.renders.push([command, parameter]);
      return { getFormData: formData, getSelection: selection }[command];
    },
  };
  const modal = { show: () => {}, update: () => {}, allowEscape: () => {} };
  const response = async () => ({ status, data });
  const model = {
    activeProgram: { id: "p-1" },
    updateOnGppNormalObservation: response,
    createTooObservation: response,
    saveNormalObservation: response,
    fetchObservations: async () => {
      calls.refreshed += 1;
      return answered;
    },
    fetchTooConfigurations: async () => {},
    getNormalObservation: () => observation,
    enumFieldOptions: () => ({}),
  };
  new GPPController(model, view, { modal });

  callbacks[event]();
  await new Promise((resolve) => setTimeout(resolve));
  return calls;
}

const rendered = ({ renders }, command) =>
  renders.filter(([name]) => name === command).map(([, parameter]) => parameter);

test.each(["Success", "Partial Success"])(
  "a %s loads the observations again and clears the form",
  async (status) => {
    const calls = await send({ status: 201, data: answer(status) });

    expect(calls.refreshed).toBe(1);
    expect(rendered(calls, "resetNormalObservations")).toEqual([{ keepForm: false }]);
    expect(rendered(calls, "resetTooObservations")).toEqual([{ keepForm: false }]);
    expect(rendered(calls, "restoreSelection")).toHaveLength(0);
  },
);

test.each([
  ["an update", "updateObservation"],
  ["a creation", "createAndSaveTooObservation"],
  ["a save in GOATS", "saveObservation"],
])("%s that failed loads them again and keeps the form to fix it", async (_, event) => {
  const selection = { normal: "o-3a7", too: "", disabled: [false, false, true] };
  const calls = await send({
    status: 400,
    data: answer("Failure"),
    selection,
    event,
  });

  expect(calls.refreshed).toBe(1);
  expect(rendered(calls, "resetNormalObservations")).toEqual([{ keepForm: true }]);
  expect(rendered(calls, "resetTooObservations")).toEqual([{ keepForm: true }]);
  expect(rendered(calls, "restoreSelection")).toEqual([selection]);
  expect(rendered(calls, "clearObservationForm")).toHaveLength(0);
  // The lists are selected in once they are loaded.
  expect(calls.renders.at(-1)[0]).toBe("restoreSelection");
});

test("an observation deleted since leaves no form", async () => {
  const calls = await send({
    status: 400,
    data: answer("Failure"),
    observation: null,
  });

  expect(calls.renders.slice(-2).map(([name]) => name)).toEqual([
    "disableObservationButtons",
    "clearObservationForm",
  ]);
});

test.each(["ONGOING", "SUSPENDED", "COMPLETED"])(
  "an observation %s since shows its own form",
  async (state) => {
    const observation = { id: "o-3a7", workflow: { value: { state } } };
    const calls = await send({
      status: 400,
      data: answer("Failure"),
      observation,
    });

    expect(rendered(calls, "updateNormalObservation")).toEqual([
      { observation, fieldOptions: {} },
    ]);
  },
);

test.each([
  ["GPP does not answer", { answered: false, observation: null }],
  [
    "a ToO configuration is selected",
    { selection: { normal: "", too: "c-1", disabled: [true, true, false] }, observation: null },
  ],
])("the form is kept when %s", async (_, options) => {
  const calls = await send({
    status: 400,
    data: answer("Failure"),
    ...options,
  });

  expect(rendered(calls, "restoreSelection")).toHaveLength(1);
  expect(rendered(calls, "clearObservationForm")).toHaveLength(0);
});

test.each([
  ["ONGOING", true],
  ["SUSPENDED", true],
  ["COMPLETED", true],
  ["READY", false],
  ["DEFINED", false],
  [undefined, false],
])("an observation in %p cannot be edited: %p", (state, locked) => {
  const GPPView = buildWindow().eval("GPPView");

  expect(GPPView.isLocked({ workflow: { value: { state } } })).toBe(locked);
});

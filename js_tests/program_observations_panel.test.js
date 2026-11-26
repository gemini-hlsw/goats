const { JSDOM } = require("jsdom");
const { js_dir } = require("./testConfig.js");
const fs = require("fs");
const path = require("path");

function buildPanel() {
  const { window } = new JSDOM("<!DOCTYPE html><body></body>", {
    runScripts: "dangerously",
  });
  [
    path.join(js_dir, "../tom-select/tom-select.base.js"),
    path.join(js_dir, "utils.js"),
    path.join(js_dir, "gpp/program_observations_panel.js"),
  ].forEach((file) => {
    const script = window.document.createElement("script");
    script.textContent = fs.readFileSync(file, "utf8");
    window.document.head.appendChild(script);
  });
  const ProgramObservationsPanel = window.eval("ProgramObservationsPanel");
  const panel = new ProgramObservationsPanel(window.document.body);
  const find = (id) => window.document.getElementById(id);
  return { panel, window, find };
}

const observations = [
  { id: "o-1", title: "One" },
  { id: "o-2", title: "Two" },
  { id: "o-3", title: "Bias", calibrationRole: "BIAS" },
];

/** Select an observation as the user does, then load the list again. */
function reload(selected, loaded) {
  const { panel, window, find } = buildPanel();
  const told = [];
  panel.onNormalSelect((id) => told.push(id));
  panel.updateNormalObservations(observations);
  panel.updateTooConfigurations([]);
  find("normalObservationSelect").value = selected;
  find("normalObservationSelect").dispatchEvent(new window.Event("change"));

  const { selection } = panel;
  panel.toggleAllButtons(true);
  panel.clearNormalSelect();
  panel.toggleNormalLoading(true);
  panel.updateNormalObservations(loaded);
  panel.toggleNormalLoading(false);
  panel.restoreSelection(selection);
  return { find, told, selection };
}

const disabled = (find) =>
  ["updateButton", "saveButton", "createNewButton"].map((id) => find(id).disabled);

describe("the selection, once the lists are loaded again", () => {
  test.each(["o-2", "o-3"])("is %s as before, with its buttons", (id) => {
    const { find, selection } = reload(id, observations);

    expect(selection).toEqual({ normal: id, too: "", disabled: [false, false, true] });
    expect(find("normalObservationSelect").value).toBe(id);
    expect(find("normalObservationSelect").tomselect.getValue()).toBe(id);
    expect(disabled(find)).toEqual([false, false, true]);
  });

  test("is not told to the handlers, which would render the form again", () => {
    const { told } = reload("o-2", observations);

    expect(told).toEqual(["o-2"]);
  });

  test("is empty when it is no longer in the list", () => {
    const { find } = reload("o-2", observations.slice(0, 1));

    expect(find("normalObservationSelect").value).toBe("");
  });
});

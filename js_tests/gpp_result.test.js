const { JSDOM } = require("jsdom");
const { js_dir } = require("./testConfig.js");
const fs = require("fs");
const path = require("path");

/** The title and body the modal ends with, once the server answers an update. */
async function updateResult(status, data) {
  const dom = new JSDOM("<!DOCTYPE html><body></body>", {
    runScripts: "dangerously",
  });
  ["utils.js", "gpp/gpp.js"].forEach((file) => {
    const script = dom.window.document.createElement("script");
    script.textContent = fs.readFileSync(path.join(js_dir, file), "utf8");
    dom.window.document.head.appendChild(script);
  });
  const GPPController = dom.window.eval("GPPController");

  const callbacks = {};
  const view = {
    bindCallback: (event, handler) => (callbacks[event] = handler),
    render: (command) => (command === "getFormData" ? {} : undefined),
  };
  const model = {
    activeProgram: { id: "p-1" },
    updateOnGppNormalObservation: async () => ({ status, data }),
    fetchObservations: async () => {},
    fetchTooConfigurations: async () => {},
  };
  const modal = { show: () => {}, update: (shown) => Object.assign(modal, { shown }) };
  new GPPController(model, view, { modal });

  callbacks.updateObservation();
  await new Promise((resolve) => setTimeout(resolve));
  return modal.shown;
}

const messages = [{ stage: "Update Observation", status: "Success", message: "Done." }];

test.each([
  [201, "Observation updated"],
  [400, "Observation updated, but not set to Defined"],
])("a %i answer is titled with what happened", async (status, summary) => {
  const { title } = await updateResult(status, { status: "", summary, messages });

  expect(title).toBe(summary);
});

test.each([
  [201, "Observation Updated on GPP"],
  [400, "Observation Update Result"],
])("a %i answer that does not say keeps its usual title", async (status, usual) => {
  const { title } = await updateResult(status, { status: "", messages });

  expect(title).toBe(usual);
});

test("what happened is shown as text", async () => {
  const { title } = await updateResult(400, { summary: "<b>No</b>", messages });

  expect(title).toBe("&lt;b&gt;No&lt;/b&gt;");
});

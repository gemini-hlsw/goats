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

const said = (element) => element?.textContent.replace(/\s+/g, " ").trim() ?? "";

/** Each step as [name, state, what it says]. */
function readSteps(root) {
  return [...root.querySelectorAll(".gpp-step")].map((step) => [
    step.querySelector(".gpp-step-name").firstChild.textContent,
    step.className.match(/gpp-step-(done|error|warning|running|none)/)[1],
    said(step.querySelector(".gpp-step-text")),
  ]);
}

/** What the card under the steps says, as [why, its notes and reasons]. */
function readWhy(root) {
  return [...root.querySelectorAll(".gpp-result-why > .gpp-why")].map((why) => [
    said(why.querySelector(".gpp-why-lead")),
    [...why.querySelectorAll(".gpp-why-note, .gpp-result-reasons li")].map(said),
  ]);
}

/** The steps the card points to. */
const explained = (root) =>
  [...root.querySelectorAll(".gpp-step-explained .gpp-step-name")].map(
    (name) => name.firstChild.textContent,
  );

/** Render a request that is running. */
function running(actionName, messages, id = "o-3a7") {
  const window = buildWindow();
  const GPPController = window.eval("GPPController");
  const { title, body, footer } = GPPController.prototype.renderRunning(
    GPPController.ACTIONS[actionName],
    messages,
    id,
  );
  window.document.body.innerHTML = `<h1>${title}</h1>${body}<footer>${footer}</footer>`;
  return window.document;
}

/** Render the result of a request. */
function result(actionName, data) {
  const window = buildWindow();
  const GPPController = window.eval("GPPController");
  const { title, body } = GPPController.prototype.renderResult(
    GPPController.ACTIONS[actionName],
    data,
  );
  window.document.body.innerHTML = `<h1>${title}</h1>${body}`;
  return window.document;
}

const ended = (stage, message, status = "Success", { label = "", details = [] } = {}) => ({
  stage,
  status,
  message,
  label,
  details,
});
const error = (text) => ({ severity: "error", text });
const checked = [
  ended("Credentials Check", "Checked"),
  ended("Data Normalization", "Checked"),
  ended("Data Validation", "Checked"),
];
const updated = [
  ...checked,
  ended("Update Sidereal Target", "Updated"),
  ended("Update Observation", "o-3a7 updated"),
];
const created = [
  ...checked,
  ended("Create Sidereal Target", "Created"),
  ended("Create Observation", "o-4f2 created"),
];
const undefinedState = ended("Update Workflow State", "o-3a7 is Undefined", "Warning", {
  label: "Undefined",
  details: [
    error("Please select a science band."),
    { severity: "warning", text: "Likelihood is 9%." },
  ],
});

describe("while a request runs", () => {
  test("the first step says what it is doing and the rest wait", () => {
    expect(readSteps(running("update", []))).toEqual([
      ["GPP login", "running", "Checking"],
      ["Form", "none", ""],
      ["Target", "none", ""],
      ["Observation", "none", ""],
      ["State", "none", ""],
    ]);
  });

  test("a step that ended says what happened and the next one what it is doing", () => {
    expect(readSteps(running("update", updated.slice(0, 4))).slice(2)).toEqual([
      ["Target", "done", "Updated"],
      ["Observation", "running", "Updating o-3a7"],
      ["State", "none", ""],
    ]);
  });

  test("a new observation is named once GPP gives it an ID", () => {
    expect(readSteps(running("create", created.slice(0, 4), null))[3]).toEqual([
      "Observation",
      "running",
      "Creating",
    ]);
    expect(readSteps(running("create", created, null)).slice(3)).toEqual([
      ["Observation", "done", "o-4f2 created"],
      ["State", "running", "Recalculating"],
      ["GOATS", "none", ""],
    ]);
  });

  test("the window says to keep it open, and how long the state can take", () => {
    const note = (messages) => said(running("update", messages).querySelector("footer"));
    const keep = "Don't close or reload this page until it finishes.";

    expect(note(updated.slice(0, 4))).toBe(keep);
    expect(note(updated)).toBe(`GPP can take up to a minute. ${keep}`);
  });

  test("only the step that just ended lights up", () => {
    const latest = running("update", updated).querySelectorAll(".gpp-step-latest");

    expect([...latest].map((step) => said(step.querySelector(".gpp-step-text")))).toEqual([
      "o-3a7 updated",
    ]);
  });

  test("a target that failed does not stop an update", () => {
    const doc = running("update", [
      ...checked,
      ended("Update Sidereal Target", "Not updated", "Error"),
    ]);

    expect(readSteps(doc).slice(2, 4)).toEqual([
      ["Target", "error", "Not updated"],
      ["Observation", "running", "Updating o-3a7"],
    ]);
  });

  test.each([
    ["a form", "update", [ended("Credentials Check", "Checked"), ended("Data Validation", "Fix", "Error")]],
    ["a new target", "create", [...checked, ended("Create Sidereal Target", "No", "Error")]],
  ])("%s that failed runs nothing after it", (_, action, messages) => {
    const states = readSteps(running(action, messages)).map(([, state]) => state);

    expect(states).not.toContain("running");
  });

  test("a calibration has no target or observation to update", () => {
    expect(readSteps(running("calibration", checked)).map(([name]) => name)).toEqual([
      "GPP login",
      "Form",
      "State",
    ]);
  });
});

describe("once a request ended", () => {
  test("the title says what happened, in the tone of the outcome", () => {
    const doc = result("update", {
      status: "Success",
      summary: "Observation updated",
      messages: [...updated, ended("Update Workflow State", "Ready")],
    });

    expect(said(doc.querySelector("h1"))).toBe("Observation updated");
    expect(doc.querySelector(".gpp-result-title").classList).toContain("gpp-result-success");
    expect(doc.querySelector(".gpp-result").getAttribute("role")).toBe("status");
    expect(readSteps(doc).at(-1)).toEqual(["State", "done", "Ready"]);
  });

  test("a request that went through has nothing to explain", () => {
    const doc = result("update", {
      status: "Success",
      summary: "Observation updated",
      messages: [...updated, ended("Update Workflow State", "Ready")],
    });

    expect(doc.querySelector(".gpp-result-why")).toBeNull();
    expect(explained(doc)).toEqual([]);
  });

  test("what needs attention says why, pointing to its step", () => {
    const doc = result("update", {
      status: "Partial Success",
      summary: "Observation updated",
      messages: [...updated, undefinedState],
    });

    expect(doc.querySelector(".gpp-result-title").classList).toContain("gpp-result-warning");
    expect(doc.querySelector(".gpp-result").classList).toContain("gpp-result-warning");
    expect(doc.querySelector(".gpp-result").getAttribute("role")).toBe("alert");
    expect(readSteps(doc).at(-1)).toEqual(["State", "warning", "Undefined"]);
    expect(explained(doc)).toEqual(["State"]);
    expect(readWhy(doc)).toEqual([
      [
        "o-3a7 is Undefined:",
        ["Please select a science band.", "Warning Likelihood is 9%."],
      ],
    ]);
    expect(said(doc.querySelector(".gpp-result-tag"))).toBe("Warning");
  });

  test.each([
    "Ready",
    "Defined",
    "Inactive",
    "Ongoing",
    "Suspended",
    "Completed",
    "Unapproved",
    "Undefined",
  ])("%s stands out in what is said of the state", (state) => {
    const doc = result("update", {
      status: "Partial Success",
      summary: "",
      messages: [...updated, { ...undefinedState, message: `o-3a7 is ${state}` }],
    });

    expect([...doc.querySelectorAll(".gpp-why-lead b")].map(said)).toEqual([state]);
  });

  test("a step that says it all is not explained", () => {
    const doc = result("save", {
      status: "Partial Success",
      summary: "Observation already in GOATS",
      messages: [
        ...checked.slice(1),
        ended("Save Observation in GOATS", "Already in GOATS", "Warning"),
      ],
    });

    expect(readSteps(doc).at(-1)).toEqual(["GOATS", "warning", "Already in GOATS"]);
    expect(readWhy(doc)).toEqual([]);
  });

  test("a step that failed in part takes the tone of the outcome", () => {
    const refused = ended("Update Workflow State", "GPP did not set it", "Error", {
      label: "Not set to Ready",
    });
    const icon = (status) =>
      result("update", { status, summary: "", messages: [...updated, refused] }).querySelector(
        ".gpp-step-error i",
      ).classList;

    expect(icon("Partial Success")).toContain("fa-circle-exclamation");
    expect(icon("Failure")).toContain("fa-circle-xmark");
  });

  test("a step that was not reached says nothing, left out or not", () => {
    const doc = result("create", {
      status: "Failure",
      summary: "Observation not created",
      messages: [
        ...created.slice(0, 4),
        ended("Create Observation", "GPP did not accept the observation", "Error", {
          label: "Refused",
          details: [error("A grating is required.")],
        }),
      ],
    });

    expect(readSteps(doc).slice(2)).toEqual([
      ["Target", "done", "Created"],
      ["Observation", "error", "Refused"],
      ["State", "none", ""],
      ["GOATS", "none", ""],
    ]);
    expect(readWhy(doc)).toEqual([
      ["GPP did not accept the observation:", ["A grating is required."]],
    ]);
    const skipped = result("update", {
      status: "Failure",
      summary: "",
      messages: [...updated, ended("Update Workflow State", "Not attempted", "Skipped")],
    });
    expect(readSteps(skipped).at(-1)).toEqual(["State", "none", ""]);
    expect(readWhy(skipped)).toEqual([]);
  });

  test("several problems are each explained, in the order of their steps", () => {
    const doc = result("create", {
      status: "Partial Success",
      summary: "Observation created, with problems",
      messages: [
        ...created,
        ended("Update Workflow State", "GPP did not set o-4f2 to Defined", "Error", {
          label: "Not set to Defined",
          details: [error("Select a band.")],
        }),
        ended("Save Observation in GOATS", "GOATS did not save o-4f2", "Error", {
          label: "Not saved",
          details: [error("Database is locked.")],
        }),
      ],
    });

    expect(readSteps(doc).slice(4)).toEqual([
      ["State", "error", "Not set to Defined"],
      ["GOATS", "error", "Not saved"],
    ]);
    expect(explained(doc)).toEqual(["State", "GOATS"]);
    expect(readWhy(doc)).toEqual([
      ["GPP did not set o-4f2 to Defined:", ["Select a band."]],
      ["GOATS did not save o-4f2:", ["Database is locked."]],
    ]);
  });

  test("two steps that failed for the same reason are explained once, naming both", () => {
    const why = {
      label: "No permission",
      details: [{ severity: "note", text: "Editing needs the PI role." }],
    };
    const doc = result("update", {
      status: "Failure",
      summary: "Observation not updated",
      messages: [
        ...checked,
        ended("Update Sidereal Target", "Your GPP account cannot edit t-2b9", "Error", why),
        ended("Update Observation", "Your GPP account cannot edit o-3a7", "Error", why),
      ],
    });

    expect(explained(doc)).toEqual(["Target", "Observation"]);
    expect(readWhy(doc)).toEqual([
      ["Your GPP account cannot edit t-2b9 or o-3a7.", ["Editing needs the PI role."]],
    ]);
  });

  test("two steps that say different things for the same reasons keep the last", () => {
    const why = { label: "Refused", details: [error("Not authorized.")] };
    const doc = result("update", {
      status: "Partial Success",
      summary: "Observation updated, with problems",
      messages: [
        ...checked,
        ended("Update Sidereal Target", "GPP did not accept the changes to t-2b9", "Error", why),
        ended("Update Observation", "o-3a7 updated", "Success"),
        ended(
          "Update Workflow State",
          "o-3a7 is Undefined. GPP could not change its state to Ready",
          "Error",
          why,
        ),
      ],
    });

    expect(explained(doc)).toEqual(["Target", "State"]);
    expect(readWhy(doc)).toEqual([
      ["o-3a7 is Undefined. GPP could not change its state to Ready:", ["Not authorized."]],
    ]);
  });

  test("two steps that give no reasons are each explained", () => {
    const why = { label: "Deleted" };
    const doc = result("update", {
      status: "Failure",
      summary: "Observation not updated",
      messages: [
        ...checked,
        ended("Update Sidereal Target", "t-2b9 was deleted in GPP", "Error", why),
        ended("Update Observation", "o-3a7 was deleted in GPP", "Error", why),
      ],
    });

    expect(readWhy(doc)).toEqual([
      ["t-2b9 was deleted in GPP.", []],
      ["o-3a7 was deleted in GPP.", []],
    ]);
  });

  test("a form that was normalized but not valid says what to fix", () => {
    const doc = result("update", {
      status: "Failure",
      summary: "Observation not sent to GPP",
      messages: [
        ...checked.slice(0, 2),
        ended("Data Validation", "Fix these fields of o-3a7 and try again", "Error", {
          label: "Not valid",
          details: [error("Band: Required.")],
        }),
      ],
    });

    expect(readSteps(doc)[1]).toEqual(["Form", "error", "Not valid"]);
    expect(readWhy(doc)).toEqual([
      ["Fix these fields of o-3a7 and try again:", ["Band: Required."]],
    ]);
  });

  test("a reason that is a sentence already keeps its end", () => {
    const doc = result("update", {
      status: "Failure",
      summary: "",
      messages: [
        ended("Credentials Check", "No credentials.", "Error", { label: "Not configured" }),
      ],
    });

    expect(readWhy(doc)).toEqual([["No credentials.", []]]);
  });

  test("the IDs of observations and targets are set apart, and nothing else is", () => {
    const doc = result("update", {
      status: "Failure",
      summary: "",
      messages: [
        ended("Update Observation", "o-3a7 and t-2b9 of p-1, to-5, o-ring, t-shirt", "Error", {
          label: "o-4f2 not updated",
        }),
      ],
    });

    expect([...doc.querySelectorAll(".gpp-result-id")].map(said)).toEqual([
      "o-4f2",
      "o-3a7",
      "t-2b9",
    ]);
  });

  test("texts are shown as text, not HTML", () => {
    const doc = result("update", {
      status: "Failure",
      summary: "<b>No</b>",
      messages: [
        ended("Update Observation", "Seeing <0.5 & clear", "Error", {
          label: "<u>No</u>",
          details: [error("<i>Why</i>"), { severity: "note", text: "<u>Note</u>" }],
        }),
      ],
    });

    expect(said(doc.querySelector("h1"))).toBe("<b>No</b>");
    expect(readSteps(doc)[3][2]).toBe("<u>No</u>");
    expect(readWhy(doc)).toEqual([["Seeing <0.5 & clear:", ["<u>Note</u>", "<i>Why</i>"]]]);
    expect(doc.querySelector("b, u, .gpp-why i")).toBeNull();
  });
});

describe("the modal", () => {
  /** Send an update and answer it, reporting some steps while it runs. */
  async function send({
    status,
    data,
    form = {},
    report = [],
    selection = { normal: "o-3a7", too: "", disabled: [false, false, true] },
    observation = { id: "o-3a7" },
    answered = true,
    event = "updateObservation",
  }) {
    const window = buildWindow();
    const GPPController = window.eval("GPPController");
    const formData = new window.FormData();
    Object.entries(form).forEach(([key, value]) => formData.append(key, value));
    const calls = { refreshed: 0, escape: 0, updates: [], renders: [] };
    const callbacks = {};
    const view = {
      bindCallback: (event, handler) => (callbacks[event] = handler),
      render: (command, parameter) => {
        calls.renders.push([command, parameter]);
        return { getFormData: formData, getSelection: selection }[command];
      },
    };
    const modal = {
      show: (options) => (calls.shown = options),
      update: (options) => calls.updates.push(options),
      allowEscape: () => (calls.escape += 1),
    };
    const progress = (detail) =>
      window.document.dispatchEvent(new window.CustomEvent("gpp:progress", { detail }));
    const answer = async (sent) => {
      calls.sent = sent;
      report.forEach((message) =>
        progress({ progress_id: sent.get("progressId"), ...message }),
      );
      progress({ progress_id: "another tab", ...ended("Update Observation", "o-9 updated") });
      return { status, data };
    };
    const model = {
      activeProgram: { id: "p-1" },
      updateOnGppNormalObservation: answer,
      createTooObservation: answer,
      saveNormalObservation: answer,
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
    // Nothing listens once the request ended.
    const before = calls.updates.length;
    progress({ progress_id: calls.sent.get("progressId"), ...ended("Data Validation", "Late") });
    expect(calls.updates).toHaveLength(before);
    return calls;
  }

  const data = { status: "Success", summary: "Observation updated", messages: updated };

  test("stays open while the request runs and shows its result", async () => {
    const calls = await send({ status: 201, data, form: { hiddenObservationIdInput: "o-3a7" } });

    expect(calls.shown.title).toContain("Updating observation");
    expect(calls.shown.title).not.toContain("…");
    expect(calls.shown).toMatchObject({ backdrop: "static", keyboard: false });
    expect(calls.shown.footer).toContain("Don't close or reload this page");
    expect(calls.updates).toHaveLength(1);
    expect(calls.updates[0].title).toContain("Observation updated");
    expect(calls.updates[0].footer).toBe("");
    expect(calls.escape).toBe(1);
  });

  test("follows the steps of its own request", async () => {
    const calls = await send({
      status: 201,
      data,
      form: { hiddenObservationIdInput: "o-3a7" },
      report: checked.slice(0, 2),
    });

    expect(calls.updates).toHaveLength(3);
    expect(calls.updates[1].body).toContain("gpp-step-done gpp-step-latest");
    expect(calls.updates[1].body).not.toContain("o-9");
  });

  test("draws its note again only when it changes", async () => {
    const calls = await send({
      status: 201,
      data,
      form: { hiddenObservationIdInput: "o-3a7" },
      report: updated,
    });

    const notes = calls.updates.slice(0, -1).map(({ footer }) => footer);
    expect(notes.slice(0, -1)).toEqual([undefined, undefined, undefined, undefined]);
    expect(notes.at(-1)).toContain("GPP can take up to a minute");
  });

  test("of a calibration, only its state is followed", async () => {
    const calls = await send({ status: 201, data, form: { isCalibration: "true" } });

    expect(calls.shown.body).not.toContain("Target");
  });

  test.each([
    [500, "Request failed (500)"],
    [200, "Unable to confirm the result"],
  ])("a %i answer without messages is shown as it came", async (status, title) => {
    const calls = await send({ status, data: { detail: "<b>boom</b>" } });

    expect(calls.updates.at(-1).title).toContain(title);
    expect(calls.updates.at(-1).body).toContain("&lt;b&gt;boom");
    expect(calls.escape).toBe(1);
  });
});

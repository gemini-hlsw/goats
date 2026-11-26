const { JSDOM } = require("jsdom");
const { js_dir } = require("./testConfig.js");
const fs = require("fs");
const path = require("path");

/** A ModalManager in a fresh page, and its footer element. */
function modal() {
  const dom = new JSDOM("<!DOCTYPE html><body></body>", { runScripts: "dangerously" });
  const script = dom.window.document.createElement("script");
  script.textContent = fs.readFileSync(path.join(js_dir, "modal_manager.js"), "utf8");
  dom.window.document.head.appendChild(script);
  const ModalManager = dom.window.eval("ModalManager");
  const manager = new ModalManager(dom.window.document.body);
  return { manager, footer: dom.window.document.querySelector(".modal-footer") };
}

describe("ModalManager.update", () => {
  test("shows a footer with content", () => {
    const { manager, footer } = modal();

    manager.update({ footer: "<p>Keep this window open.</p>" });

    expect(footer.classList).not.toContain("d-none");
    expect(footer.textContent).toBe("Keep this window open.");
  });

  test("hides an emptied footer, as show() does", () => {
    const { manager, footer } = modal();
    manager.update({ footer: "<p>Keep this window open.</p>" });

    manager.update({ footer: "" });

    expect(footer.classList).toContain("d-none");
  });

  test("leaves the footer as it is when not given one", () => {
    const { manager, footer } = modal();
    manager.update({ footer: "<p>Note</p>" });

    manager.update({ title: "Done." });

    expect(footer.classList).not.toContain("d-none");
  });
});

describe("ModalManager.allowEscape", () => {
  const escape = (element) =>
    element.dispatchEvent(new element.ownerDocument.defaultView.KeyboardEvent("keydown", { key: "Escape" }));

  test("Esc does not close a modal until it is allowed to", () => {
    const { manager, footer } = modal();
    const element = footer.closest(".modal");
    manager.hide = jest.fn();

    escape(element);
    expect(manager.hide).not.toHaveBeenCalled();

    manager.allowEscape();
    escape(element);
    expect(manager.hide).toHaveBeenCalledTimes(1);
  });
});

describe("ModalManager.update smooth", () => {
  test("grows from the old height to the new one instead of jumping", () => {
    const { manager, footer } = modal();
    const content = footer.closest(".modal-content");
    const heights = [200, 260];
    content.getBoundingClientRect = () => ({ height: heights.shift() });
    content.animate = jest.fn();

    manager.update({ body: "<p>Result</p>", smooth: true });

    expect(content.animate).toHaveBeenCalledWith(
      [
        { height: "200px", overflow: "hidden" },
        { height: "260px", overflow: "hidden" },
      ],
      { duration: 200, easing: "ease-out" },
    );
  });

  test("does not animate unless asked to", () => {
    const { manager, footer } = modal();
    const content = footer.closest(".modal-content");
    content.animate = jest.fn();

    manager.update({ body: "<p>Result</p>" });

    expect(content.animate).not.toHaveBeenCalled();
  });
});

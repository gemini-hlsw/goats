const { JSDOM } = require("jsdom");
const fs = require("fs");
const path = require("path");
const { js_dir } = require("./testConfig.js");

const script = fs.readFileSync(path.join(js_dir, "navbar_menus.js"), "utf8");
const windows = [];
afterEach(() => windows.splice(0).forEach((window) => window.close()));

function build(markup) {
  const dom = new JSDOM(markup, { runScripts: "outside-only" });
  windows.push(dom.window);
  dom.window.eval(script);
  return dom.window;
}

const box = (left, width) => () => ({ left, width, top: 0, height: 20 });

const open = (window, toggle) =>
  toggle.dispatchEvent(new window.CustomEvent("show.bs.dropdown", { bubbles: true }));

test("the arrow is placed under the icon, not the middle of the toggle", () => {
  const window = build(`<ul class="navbar-tools"><li class="dropdown">
      <a id="toggle" class="dropdown-toggle"><i></i><span>grace</span></a>
    </li></ul>`);
  const toggle = window.document.getElementById("toggle");
  toggle.getBoundingClientRect = box(100, 120);
  toggle.querySelector("i").getBoundingClientRect = box(108, 20);

  open(window, toggle);

  expect(toggle.style.getPropertyValue("--menu-arrow-x")).toBe("18px");
});

test("the arrow finds the icon once Font Awesome has made it an svg", () => {
  const window = build(`<ul class="navbar-tools"><li class="dropdown">
      <a id="toggle" class="dropdown-toggle"><svg class="svg-inline--fa"></svg><span>grace</span></a>
    </li></ul>`);
  const toggle = window.document.getElementById("toggle");
  toggle.getBoundingClientRect = box(100, 120);
  toggle.querySelector("svg").getBoundingClientRect = box(110, 16);

  open(window, toggle);

  expect(toggle.style.getPropertyValue("--menu-arrow-x")).toBe("18px");
});

test("menus outside the navbar tools are left alone", () => {
  const window = build(`<div><a id="toggle" class="dropdown-toggle"><i></i></a></div>`);
  const toggle = window.document.getElementById("toggle");

  open(window, toggle);

  expect(toggle.style.getPropertyValue("--menu-arrow-x")).toBe("");
});

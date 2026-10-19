const { JSDOM } = require("jsdom");
const fs = require("fs");
const path = require("path");
const { js_dir } = require("./testConfig.js");

const script = fs.readFileSync(path.join(js_dir, "toggle_mode.js"), "utf8");
const windows = [];
afterEach(() => windows.splice(0).forEach((window) => window.close()));

const NAV_ICON = `<button id="colorThemeToggle" class="nav-link">
  <i class="fa-solid fa-sun fa-lg" data-theme-icon></i><span class="d-md-none ms-2">Theme</span>
</button>`;

function build(markup, storedTheme) {
  const dom = new JSDOM(markup, { runScripts: "outside-only", url: "https://goats.test/" });
  const { window } = dom;
  windows.push(window);
  window.matchMedia = () => ({ matches: false, addEventListener: () => {} });
  if (storedTheme) window.localStorage.setItem("theme", storedTheme);
  window.eval(script);
  window.dispatchEvent(new window.Event("DOMContentLoaded"));
  const button = window.document.getElementById("colorThemeToggle");
  return { window, button, icon: button.querySelector("[data-theme-icon]") };
}

const theme = (window) => window.document.documentElement.getAttribute("data-bs-theme");

test("the icon switches the theme", () => {
  const { window, button } = build(NAV_ICON, "light");

  button.click();
  expect(theme(window)).toBe("dark");

  button.click();
  expect(theme(window)).toBe("light");
});

test("the navbar icon swaps without losing its classes or label", () => {
  const { button, icon } = build(NAV_ICON, "dark");
  expect(icon.classList.contains("fa-sun")).toBe(true);

  button.click();

  expect(icon.classList.contains("fa-moon")).toBe(true);
  expect(icon.classList.contains("fa-lg")).toBe(true);
  expect(button.textContent).toContain("Theme");
});

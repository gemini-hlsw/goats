const { JSDOM } = require("jsdom");
const { js_dir } = require("./testConfig.js");
const path = require("path");

// Load script.
const script = new JSDOM("<!DOCTYPE html>", {
  runScripts: "dangerously",
  resources: "usable",
});
const window = script.window;
const document = window.document;

// Append the script to the document.
const scriptTag = document.createElement("script");
const scriptPath = path.join(js_dir, "gpp", "formatters.js");
scriptTag.textContent = require("fs").readFileSync(scriptPath, "utf8");
document.head.appendChild(scriptTag);

const Formatters = window.eval("Formatters");

test.each([
  ["GOATS:25.9.0:Rubin", "Rubin"],
  ["GOATS:25.9.0:Pan-STARRS", "Pan-STARRS"],
  // No survey suffix, or a subtitle GOATS did not write.
  ["GOATS:25.9.0", ""],
  ["GOATS", ""],
  ["a subtitle written by the PI", ""],
  [undefined, ""],
  [null, ""],
])("discoverySurveyFromSubtitle(%p) is %p", (subtitle, expected) => {
  expect(Formatters.discoverySurveyFromSubtitle(subtitle)).toBe(expected);
});

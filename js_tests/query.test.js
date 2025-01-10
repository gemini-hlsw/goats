const { JSDOM } = require("jsdom");
const { js_dir } = require("./testConfig.js");
const path  = require("path");

// Load script.
const script = new JSDOM('<!DOCTYPE html><textarea id="id_query"></textarea>', {
  runScripts: "dangerously",
  resources: "usable"
});
const window = script.window;
const document = window.document;

// Append the script to the document.
const scriptTag = document.createElement("script");
const scriptPath = path.join(js_dir, "query.js");
scriptTag.textContent = require("fs").readFileSync(scriptPath, "utf8");
document.head.appendChild(scriptTag);

// Run tests.
test("Testing query", () => {
  // Trigger the event.
  const textarea = document.getElementById("id_query");
  textarea.value = '{"key": "value"}';
  const event1 = new window.Event("blur");
  textarea.dispatchEvent(event1);

  // Check the result.
  expect(textarea.value).toBe('{\n    "key": "value"\n}');

  textarea.value = "invalid json";
  const event2 = new window.Event("blur");
  textarea.dispatchEvent(event2);

  // Check that the "is-invalid" class was added.
  expect(textarea.classList.contains("is-invalid")).toBe(true);
});
const { JSDOM } = require("jsdom");
const { js_dir } = require("./testConfig.js");
const fs = require("fs");
const path = require("path");

/** A window with utils plus the given DRAGONS script loaded. */
function buildWindow(script_path, className) {
  const dom = new JSDOM("<!DOCTYPE html><body></body>", {
    runScripts: "dangerously",
  });
  for (const file of ["utils.js", script_path]) {
    const script = dom.window.document.createElement("script");
    script.textContent = fs.readFileSync(path.join(js_dir, file), "utf8");
    dom.window.document.head.appendChild(script);
  }
  return className ? dom.window.eval(className) : dom.window;
}

const processedFile = (name, last_modified) => ({ name, last_modified });
const availableFile = (product_id, created) => ({ product_id, created });

describe("processed files", () => {
  const View = () => buildWindow("dragons_app/processed_files.js", "ProcessedFilesView");
  const files = [
    processedFile("b.fits", "2024-01-02 00:00:00"),
    processedFile("a.fits", "2024-01-03 00:00:00"),
    processedFile("c.fits", "2024-01-01 00:00:00"),
  ];

  test("the server's order is kept until a sort is asked for", () => {
    const view = new (View())(null, {});

    expect(view._sorted(files)).toBe(files);
  });

  test("sorting by date leaves the given rows untouched", () => {
    const view = new (View())(null, {});
    view.sortDirection = "desc";

    view._sorted(files);

    expect(files.map((file) => file.name)).toEqual(["b.fits", "a.fits", "c.fits"]);
  });

  test.each([
    ["desc", ["a.fits", "b.fits", "c.fits"]],
    ["asc", ["c.fits", "b.fits", "a.fits"]],
  ])("sorts %s by last modified", (direction, expected) => {
    const view = new (View())(null, {});
    view.sortDirection = direction;

    expect(view._sorted(files).map((file) => file.name)).toEqual(expected);
  });

  test.each(["asc", "desc"])("files sharing a date stay alphabetical (%s)", (dir) => {
    const view = new (View())(null, {});
    view.sortDirection = dir;
    const tied = [
      processedFile("z.fits", "2024-01-01 00:00:00"),
      processedFile("a.fits", "2024-01-01 00:00:00"),
    ];

    expect(view._sorted(tied).map((file) => file.name)).toEqual(["a.fits", "z.fits"]);
  });
});

describe("available files", () => {
  const View = () => buildWindow("dragons_app/files_table.js", "FilesTableView");
  const files = [
    availableFile("b.fits", "2024-01-02 00:00:00"),
    availableFile("a.fits", "2024-01-03 00:00:00"),
    availableFile("c.fits", "2024-01-01 00:00:00"),
  ];

  test("the server's order is kept until a sort is asked for", () => {
    const view = new (View())(null, {});

    expect(view._sorted(files)).toBe(files);
  });

  test.each([
    ["desc", ["a.fits", "b.fits", "c.fits"]],
    ["asc", ["c.fits", "b.fits", "a.fits"]],
  ])("sorts %s by created", (direction, expected) => {
    const view = new (View())(null, {});
    view.sortDirection = direction;

    expect(view._sorted(files).map((file) => file.product_id)).toEqual(expected);
  });

  test("a file with no date sorts last either way", () => {
    const view = new (View())(null, {});
    const mixed = [availableFile("no-date.fits", null), ...files];

    for (const direction of ["asc", "desc"]) {
      view.sortDirection = direction;
      const names = view._sorted(mixed).map((file) => file.product_id);
      expect(names[names.length - 1]).toBe("no-date.fits");
    }
  });
});

describe("sorting through the rendered controls", () => {
  let window;
  afterEach(() => window?.close());

  function renderTable(processed, files) {
    window = buildWindow(
      `dragons_app/${processed ? "processed_files" : "files_table"}.js`, null
    );
    window.bootstrap = { Tooltip: class { static getInstance() { return null; } } };
    const options = { id: "testFiles" };
    const Template = window.eval(processed ? "ProcessedFilesTemplate" : "FilesTableTemplate");
    const View = window.eval(processed ? "ProcessedFilesView" : "FilesTableView");
    const template = processed ? new Template(options) :
      new Template({ idPrefix: "test" }, options);
    const view = new View(template, options);
    view.render("create", {
      parentElement: window.document.body,
      data: processed ? files : { All: { files, count: files.length } },
    });
    return view;
  }

  const files = [
    { id: 1, product_id: "a.fits", created: "2024-01-01T00:00:00Z" },
    { id: 2, product_id: "b.fits", created: "2024-01-02T00:00:00Z" },
  ];

  test("first click sorts existing files and preserves the selection", () => {
    const view = renderTable(false, files);
    const originalRow = view.tbody.rows[0];
    const checkbox = originalRow.querySelector("input");
    checkbox.checked = false;
    view.render("setSelectAllCheckbox");
    const button = view.thead.querySelector('[data-action="sortByDate"]');
    button.click();
    expect(Array.from(view.tbody.rows, row => row.dataset.fileId)).toEqual(["2", "1"]);
    expect(view.tbody.rows[1]).toBe(originalRow);
    expect(checkbox.checked).toBe(false);
    expect(view.toggleFilesCheckbox.checked).toBe(false);
    expect(view.tbody.querySelectorAll("input:checked")).toHaveLength(1);
    button.click();
    expect(view.tbody.rows[0]).toBe(originalRow);
    expect(checkbox.checked).toBe(false);
    expect(button.querySelector(".fa-arrow-up-short-wide")).not.toBeNull();
    expect(originalRow.cells[1].textContent).toBe("2024-01-01 00:00:00");
  });

  test("updates keep the chosen order and an empty table can be sorted", () => {
    const view = renderTable(false, []);
    const button = view.thead.querySelector('[data-action="sortByDate"]');
    button.click();
    expect(view.tbody.querySelectorAll("input")).toHaveLength(0);
    view.render("updateFiles", { data: files });
    expect(Array.from(view.tbody.rows, row => row.dataset.fileId)).toEqual(["2", "1"]);
  });

  test("processed-file sorting retains row nodes and event listeners", () => {
    const view = renderTable(true, [
      processedFile("a.fits", "2024-01-01 00:00:00"),
      processedFile("b.fits", "2024-01-02 00:00:00"),
    ]);
    const originalRow = view.tbody.rows[0];
    const listener = jest.fn();
    originalRow.addEventListener("click", listener);
    const button = view.thead.querySelector('[data-action="sortByDate"]');
    button.click();
    expect(view.tbody.rows[1]).toBe(originalRow);
    originalRow.click();
    expect(listener).toHaveBeenCalledTimes(1);
    button.click();
    expect(view.tbody.rows[0]).toBe(originalRow);
  });

  test("ISO dates sort by instant, including microseconds and offsets", () => {
    const view = renderTable(false, []);
    view.sortDirection = "asc";
    const data = [
      availableFile("a", "2024-01-01T00:00:00.000002Z"),
      availableFile("z", "2024-01-01T00:00:00.000001Z"),
      availableFile("m", "2024-01-01T00:00:00Z"),
      availableFile("b", "2024-01-01T00:00:00+01:00"),
    ];
    expect(view._sorted(data).map(file => file.product_id)).toEqual(["b", "m", "z", "a"]);
  });
});

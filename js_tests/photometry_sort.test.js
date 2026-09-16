const { JSDOM } = require("jsdom");
const { js_dir } = require("./testConfig.js");
const fs = require("fs");
const path = require("path");

/** Rows as the template renders them: pk, ISO timestamp and raw MJD. */
const row = (pk, timestamp, mjd) =>
  `<tr data-sort-pk="${pk}" data-sort-timestamp="${timestamp}" data-sort-mjd="${mjd}">` +
  `<td><input type="checkbox" class="phot-row" value="${pk}"></td><td>${timestamp}</td>` +
  `<td>${mjd}</td></tr>`;

/** A photometry table wired the way the partial wires it. */
function buildWindow(rows) {
  const header = (field, label) =>
    `<th><a href="?tab=photometry&order_photometry=-${field}">${label}` +
    `<i class="fa-solid fa-sort text-muted"></i></a></th>`;
  const dom = new JSDOM(
    `<!DOCTYPE html><body><table id="photData"><thead><tr>` +
      `${header("timestamp", "Timestamp")}${header("mjd", "MJD")}` +
      `</tr></thead><tbody>${rows.join("")}` +
      `<tr id="photDataNoMatchesRow" style="display: none;"><td>No matches found...</td></tr>` +
      `</tbody></table></body>`,
    { runScripts: "dangerously", url: "https://goats.test/targets/1/?tab=photometry" }
  );
  for (const file of ["utils.js", "photometry_sort.js"]) {
    const script = dom.window.document.createElement("script");
    script.textContent = fs.readFileSync(path.join(js_dir, file), "utf8");
    dom.window.document.head.appendChild(script);
  }
  dom.window.document.dispatchEvent(new dom.window.Event("DOMContentLoaded"));
  return dom.window;
}

/** The pk of every data row, in the order they currently sit in the DOM. */
const order = (window) =>
  Array.from(window.document.querySelectorAll("#photData tbody tr[data-sort-pk]")).map(
    (tr) => tr.dataset.sortPk
  );

const headers = (window) =>
  Array.from(window.document.querySelectorAll("#photData thead a"));

const rows = [
  row("1", "2024-01-02T00:00:00+00:00", "60311.0"),
  row("2", "2024-01-03T00:00:00+00:00", "60312.0"),
  row("3", "2024-01-01T00:00:00+00:00", "60310.0"),
];

describe("photometry table sorting", () => {
  test("the server's order is kept until a header is clicked", () => {
    const window = buildWindow(rows);
    expect(order(window)).toEqual(["1", "2", "3"]);
  });

  test("clicking Timestamp sorts newest first, then toggles to oldest first", () => {
    const window = buildWindow(rows);
    const [timestamp] = headers(window);

    timestamp.click();
    expect(order(window)).toEqual(["2", "1", "3"]);

    timestamp.click();
    expect(order(window)).toEqual(["3", "1", "2"]);
  });

  test("MJD sorts on its own column", () => {
    const window = buildWindow(rows);
    const [, mjd] = headers(window);

    mjd.click();
    expect(order(window)).toEqual(["2", "1", "3"]);
  });

  test("rows without an MJD stay last whichever way the column is sorted", () => {
    const window = buildWindow([...rows, row("4", "2024-01-04T00:00:00+00:00", "")]);
    const [, mjd] = headers(window);

    mjd.click();
    expect(order(window).at(-1)).toBe("4");

    mjd.click();
    expect(order(window).at(-1)).toBe("4");
  });

  test("the page is never reloaded and the order lands in the URL", () => {
    const window = buildWindow(rows);
    const [timestamp] = headers(window);
    const event = new window.Event("click", { bubbles: true, cancelable: true });

    timestamp.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(true);
    expect(window.location.search).toContain("order_photometry=-timestamp");
    // The tab selection the page already tracks must survive the sort.
    expect(window.location.search).toContain("tab=photometry");
  });

  test("the empty-state row is pushed back below the data", () => {
    const window = buildWindow(rows);
    headers(window)[0].click();

    const all = Array.from(window.document.querySelectorAll("#photData tbody tr"));
    expect(all.at(-1).id).toBe("photDataNoMatchesRow");
  });

  test("the sorted header shows its direction and the other one resets", () => {
    const window = buildWindow(rows);
    const [timestamp, mjd] = headers(window);

    timestamp.click();
    expect(timestamp.querySelector("i").className).toContain("fa-arrow-down-wide-short");

    mjd.click();
    expect(mjd.querySelector("i").className).toContain("fa-arrow-down-wide-short");
    expect(timestamp.querySelector("i").className).toContain("fa-sort");
  });

  test("sorting moves the existing rows, keeping their checkbox state", () => {
    const window = buildWindow(rows);
    const box = window.document.querySelector('.phot-row[value="3"]');
    box.checked = true;

    headers(window)[0].click();

    expect(window.document.querySelector('.phot-row[value="3"]').checked).toBe(true);
  });
});

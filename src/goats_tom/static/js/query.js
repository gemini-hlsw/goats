/**
 * This script adds an event listener to an element with the id "esquery".
 * When the element loses focus, it attempts to parse the content as JSON.
 * If successful, it reformats the JSON with 4 spaces indentation.
 * If the content is not valid JSON, the textarea is highlighted.
 */
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("id_query").addEventListener("blur", (event) => {
    const value = event.target.value;
    if (value !== null && value.trim() !== "") {
      try {
        const json = JSON.parse(value);
        event.target.value = JSON.stringify(json, null, 4);
        // Remove invalid class.
        event.target.classList.remove("is-invalid");
      } catch (e) {
        // Handle error - not valid JSON, add class.
        event.target.classList.add("is-invalid");
      }
    }
  });
});

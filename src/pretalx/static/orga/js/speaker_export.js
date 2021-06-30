function docReady(fn) {
    // see if DOM is already available
    if (document.readyState === "complete" || document.readyState === "interactive") {
        // call on next available tick
        setTimeout(fn, 1);
    } else {
        document.addEventListener("DOMContentLoaded", fn);
    }
}

const addHook = () => {
  const updateVisibility = () => {
    const isCSV = document.querySelector("#id_export_format input[value='csv']").checked;
    if (isCSV) {
      document.querySelector("#data-delimiter").style.display = "block"
    } else {
      document.querySelector("#data-delimiter").style.display = "none"

    }
  }
  updateVisibility()
  document.querySelectorAll("#id_export_format input").forEach(element => element.addEventListener("change", updateVisibility))
}
docReady(addHook)

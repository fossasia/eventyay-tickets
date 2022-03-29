function docReady(fn) {
    // see if DOM is already available
    if (document.readyState === "complete" || document.readyState === "interactive") {
        // call on next available tick
        setTimeout(fn, 1);
    } else {
        document.addEventListener("DOMContentLoaded", fn);
    }
}

const changeSelectAll = (e) => {
  const checkBox = document.querySelector("#select-all")
  checkBox.closest("fieldset").querySelectorAll("input[type=checkbox]").forEach(element => element.checked = checkBox.checked)
}

const addHook = () => {
  const updateVisibility = () => {
    const delimiter = document.querySelector("#data-delimiter")
    if (delimiter) {
      const isCSV = document.querySelector("#id_export_format input[value='csv']").checked;
      if (isCSV) {
        document.querySelector("#data-delimiter").style.display = "block"
      } else {
        document.querySelector("#data-delimiter").style.display = "none"
      }
    }
  }
  updateVisibility()
  document.querySelectorAll("#id_export_format input").forEach(element => element.addEventListener("change", updateVisibility))
  document.querySelector("#select-all").addEventListener("change", changeSelectAll)
}
docReady(addHook)

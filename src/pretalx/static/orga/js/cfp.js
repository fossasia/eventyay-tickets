document
  .querySelectorAll("#cfp-option-table .require input")
  .forEach(element => {
    element.addEventListener("click", ev => {
      if (ev.target.checked) {
        ev.target.parentElement.parentElement.parentElement.parentElement.querySelector(
          ".request input"
        ).checked = true
      }
    })
  })

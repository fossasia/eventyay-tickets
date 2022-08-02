document.addEventListener("DOMContentLoaded", function() {
  const updatePendingVisibility = () => {
    if (document.querySelector("#id_state").value) {
      document.querySelector("#pending").classList.remove("d-none")
    } else {
      document.querySelector("#pending").classList.add("d-none")
    }
  }
  $("#id_state").on("change", updatePendingVisibility)
  updatePendingVisibility()
})

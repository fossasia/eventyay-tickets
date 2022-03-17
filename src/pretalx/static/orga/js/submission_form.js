const updateVisibility = () => {
  if (["accepted", "confirmed"].includes(document.querySelector("#id_state").value)) {
    document.querySelector("#show-if-state").classList.remove("d-none")
  } else {
    document.querySelector("#show-if-state").classList.add("d-none")
  }
}

if (document.querySelector("#id_state")) {
  document.querySelector("#id_state").addEventListener("change", updateVisibility)
  updateVisibility()
}

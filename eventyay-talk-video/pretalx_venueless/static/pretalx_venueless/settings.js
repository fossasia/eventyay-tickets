const checkbox = document.querySelector("#id_show_join_link")
const settings = document.querySelector("#join-link-settings")
const updateVisibility = () => {
    if (checkbox.checked) {
        settings.classList.remove("d-none")
    } else {
        settings.classList.add("d-none")
    }
}
checkbox.addEventListener("change", updateVisibility)
updateVisibility()

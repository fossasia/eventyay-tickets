const reviewerInput = document.querySelector("input#id_is_reviewer")
const updateVisibility = () => {
    document.querySelector("#review-settings").classList.toggle("d-none", !reviewerInput.checked)
}
reviewerInput.addEventListener("change", updateVisibility)
updateVisibility()

document.querySelector("a#bulk-email").addEventListener("click", (event) => {
    event.preventDefault()
    document.querySelector("#single-invite").classList.add("d-none")
    document.querySelector("#bulk-invite").classList.remove("d-none")
})

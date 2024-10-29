const dateHelpText = document.getElementById("id_date_to_helptext")

const showDateHelpText = () => {
    dateHelpText.classList.remove("d-none")
}

onReady(() => {
    dateHelpText.classList.add("d-none")
    document.getElementById("id_date_to").addEventListener("change", showDateHelpText)
    document.getElementById("id_date_from").addEventListener("change", showDateHelpText)
})

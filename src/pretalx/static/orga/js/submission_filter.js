onReady(() => {
    const updatePendingVisibility = () => {
        if (document.querySelector("#id_state").value) {
            document.querySelector("#pending").classList.remove("d-none")
        } else {
            document.querySelector("#pending").classList.add("d-none")
        }
    }
    document
        .querySelector("#id_state")
        .addEventListener("change", updatePendingVisibility)
    updatePendingVisibility()
})

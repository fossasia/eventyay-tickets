/* Minimal enhancement to native modals, by making them close when the user clicks outside the dialog. */

const setupModals = () => {
    document.querySelectorAll("[data-dialog-target]").forEach((element) => {
        const outerDialogElement = document.querySelector(
            element.dataset.dialogTarget,
        )
        if (!outerDialogElement) return
        element.addEventListener("click", function (ev) {
            ev.preventDefault()
            outerDialogElement.showModal()
        })
        outerDialogElement.addEventListener("click", () => outerDialogElement.close())
        outerDialogElement.querySelector("div").addEventListener("click", (ev) => ev.stopPropagation())
    })
}

onReady(setupModals)

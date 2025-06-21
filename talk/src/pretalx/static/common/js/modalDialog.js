/* Minimal enhancement to native modals, by making them close when the user clicks outside the dialog. */

const setupModals = () => {
    document.querySelectorAll(".dialog-anchor").forEach((element) => {
        const outerDialogElement = document.querySelector(
            element.dataset.target,
        )
        if (!outerDialogElement) return
        element.addEventListener("click", function (event) {
            event.preventDefault()
            const dialogElement = document.querySelector(
                event.currentTarget.dataset.target,
            )
            dialogElement.showModal()
        })
        outerDialogElement.addEventListener("click", () => {
            outerDialogElement.close()
        })
    })
}

onReady(setupModals)

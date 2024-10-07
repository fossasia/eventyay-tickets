
const setupModals = () => {
    document.querySelectorAll('.dialog-anchor').forEach((element) => {
        const outerDialogElement = document.querySelector(element.dataset.target)
        if (!outerDialogElement) return
        element.addEventListener("click", function(event) {
            event.preventDefault()
            const dialogElement = document.querySelector(event.currentTarget.dataset.target)
            dialogElement.showModal()
        })
        outerDialogElement.addEventListener("click", () => { outerDialogElement.close() })
    })
}

document.addEventListener("DOMContentLoaded", setupModals)
if (document.readyState === 'complete' || document.readyState === 'loaded') {
    setupModals()
}

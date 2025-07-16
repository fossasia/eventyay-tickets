const performCopy = (element) => {
    navigator.clipboard.writeText(element.dataset.destination).then(() => {
        const wasTooltip = element.getAttribute('data-toggle') === 'tooltip'
        const oldTitle = element.title || ''
        element.title = 'Copied!'
        if (!wasTooltip) {
            element.setAttribute('data-toggle', 'tooltip')
        }
        setTimeout(() => {
            element.title = oldTitle
            if (!wasTooltip) {
                element.removeAttribute('data-toggle')
            }
        }, 1000)
    })
}

onReady(() => {
    document.querySelectorAll('.copyable-text').forEach((el) => {
        el.addEventListener('click', () => performCopy(el))
    })
})

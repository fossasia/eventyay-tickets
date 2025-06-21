const performCopy = (element) => {
    const input = document.createElement('input')
    input.value = element.dataset.destination
    document.body.appendChild(input)
    input.select()
    document.execCommand('copy')
    document.body.removeChild(input)
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
}

onReady(() => {
    document.querySelectorAll('.copyable-text').forEach((el) => {
        el.addEventListener('click', () => performCopy(el))
    })
})

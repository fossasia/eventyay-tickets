const makeCollapsed = (controller, element, collapsed) => {
    controller.setAttribute('aria-expanded', !collapsed)
    element.setAttribute('aria-hidden', collapsed)
    if (collapsed) {
        element.classList.remove('show')
    } else {
        element.classList.add('show')
    }
}


const handleCollapse = (controller, target) => {
    const wasVisible = controller.getAttribute('aria-expanded') === 'true'
    const accordion = target.getAttribute('data-parent')
    if (accordion) {
        document.querySelectorAll(`[data-parent="${accordion}"]`).forEach(element => {
            makeCollapsed(document.querySelector(`[data-target="#${element.id}"]`), element, true)
        })
    }
    makeCollapsed(controller, target, wasVisible)
}

const setupCollapse = (element) => {
    const target = document.querySelector(element.getAttribute('data-target'))
    if (!target) return
    element.addEventListener('click', () => handleCollapse(element, target))
    if (target.classList.contains('show')) {
        makeCollapsed(element, target, false)
    }
}

const initCollapse = () => {
    document.querySelectorAll('[data-toggle="collapse"]').forEach(element => {
        setupCollapse(element)
    })
}
onReady(initCollapse)

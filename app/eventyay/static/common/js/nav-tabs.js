const updateTabActiveState = () => {
    const hash = window.location.hash
    const ticketsSection = document.getElementById('tickets')
    const infoTab = document.getElementById('nav-tab-info')
    const ticketsTab = document.getElementById('nav-tab-tickets')

    if (!infoTab || !ticketsTab || !ticketsSection) return

    if (hash === '#tickets') {
        infoTab.classList.remove('active', 'underline')
        ticketsTab.classList.add('active', 'underline')
    } else {
        infoTab.classList.add('active', 'underline')
        ticketsTab.classList.remove('active', 'underline')
    }
}

const alignTicketsSection = () => {
    if (window.location.hash !== '#tickets') return

    const targetElement = document.querySelector('#ticket-list h3') || document.getElementById('tickets')
    const stickyTabs = document.querySelector('.presale-sticky-tabs-wrap')

    if (targetElement) {
        const headerHeight = stickyTabs ? stickyTabs.getBoundingClientRect().height : 0
        const offsetPosition = targetElement.getBoundingClientRect().top + window.scrollY - headerHeight
        window.scrollTo({ top: offsetPosition })
    }
}

const initNavTabs = () => {
    updateTabActiveState()

    window.addEventListener('hashchange', () => {
        updateTabActiveState()
        alignTicketsSection()
    })

    const ticketsTab = document.getElementById('nav-tab-tickets')

    if (ticketsTab) {
        ticketsTab.addEventListener('click', () => {
            if (window.location.hash === '#tickets') {
                setTimeout(alignTicketsSection, 0)
            }
        })
    }

    window.addEventListener('load', alignTicketsSection)
}

if (
    document.getElementById('nav-tab-info')
    && document.getElementById('nav-tab-tickets')
    && document.getElementById('tickets')
) {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initNavTabs)
    } else {
        initNavTabs()
    }
}

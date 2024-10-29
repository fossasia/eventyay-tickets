const TAB_SELECTOR = "input[role=tab][name=tablist]"

const updateTabPanels = () => {
    const selectedTab = document.querySelector(`${TAB_SELECTOR}:checked`)
    if (!selectedTab) return
    const selectedPanel = document.getElementById(selectedTab.getAttribute("aria-controls"))
    if (!selectedPanel) return
    selectedTab.parentElement.querySelectorAll(`[role=tab][aria-selected=true]`).forEach((element) => {
        element.setAttribute("aria-selected", "false")
    })
    selectedPanel.parentElement.querySelectorAll("[role=tabpanel][aria-hidden=false]").forEach((element) => {
        element.setAttribute("aria-hidden", "true")
    })
    selectedTab.setAttribute("aria-selected", "true")
    selectedPanel.setAttribute("aria-hidden", "false")
    window.location.hash = selectedTab.id
}

const getTabFromHash = () => {
    const fragment = window.location.hash.substr(1)
    if (fragment) {
        return document.querySelector(`${TAB_SELECTOR}#${fragment}`)
    }
}

const initTabs = () => {
    // First, check if there is a tab selected by the hash. If not:
    // Fall back to the last selected tab, and failing that, the first tab

    let selectedTab = getTabFromHash()
    if (!selectedTab) { selectedTab = document.querySelector(`${TAB_SELECTOR}:checked`) }
    if (!selectedTab) { selectedTab = document.querySelector(TAB_SELECTOR) }
    if (!selectedTab) return

    selectedTab.checked = true
    updateTabPanels()

    document.querySelectorAll(`${TAB_SELECTOR}`).forEach((element) => {
        element.addEventListener('change', updateTabPanels)
    })

    // If the URL fragment changes, e.g. by navigating backwards, update the tab
    window.addEventListener('hashchange', () => {
        selectedTab = getTabFromHash()
        if (selectedTab) {
            selectedTab.checked = true
            updateTabPanels()
        }
    })
}

if (document.querySelector(TAB_SELECTOR)) {
  initTabs()
}

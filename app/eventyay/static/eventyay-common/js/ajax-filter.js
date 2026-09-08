const isFilterForm = function(form) {
    const action = form.getAttribute('action');
    if (action && action.includes('/go')) {
        return false;
    }

    return form.classList.contains('filter-form') || !!form.querySelector('.filter-form') || !!form.closest('.filter-form');
};

const getFilterForms = function(root = document) {
    return Array.from(root.querySelectorAll('form')).filter(function(form) {
        return isFilterForm(form);
    });
};

const hasAjaxResultsRegion = function(root = document) {
    return !!root.querySelector('[data-ajax-results-region]');
};

let activeRequestController = null;

const getTableContainer = function(context) {
    return context.querySelector('.table-responsive') || context.querySelector('table.table') || context.querySelector('.empty-collection');
};

const getExplicitResultsRegion = function(context) {
    return context.querySelector('[data-ajax-results-region]');
};

const getResultsContainer = function(context) {
    const explicitRegion = getExplicitResultsRegion(context);
    if (explicitRegion) {
        return explicitRegion;
    }

    const tableContainer = getTableContainer(context);
    if (!tableContainer) {
        return null;
    }

    return tableContainer.closest('.tab-pane') || tableContainer;
};

const getTabContextFromForm = function(formOrElement) {
    if (!formOrElement) {
        return {
            context: document,
            tabId: null,
        };
    }

    if (formOrElement.classList && formOrElement.classList.contains('tab-pane') && formOrElement.id) {
        return {
            context: formOrElement,
            tabId: formOrElement.id,
        };
    }

    const tabPane = formOrElement.closest ? formOrElement.closest('.tab-pane') : null;
    if (tabPane && tabPane.id) {
        return {
            context: tabPane,
            tabId: tabPane.id,
        };
    }

    return {
        context: document,
        tabId: null,
    };
};

const reinitializeBehaviors = function(resultsContainer) {
    if (typeof window.eventyayInitTimezoneUtilities === 'function') {
        window.eventyayInitTimezoneUtilities();
    }

    if (typeof window.eventyayInitStartpageToggles === 'function') {
        window.eventyayInitStartpageToggles();
    }

    if (typeof window.eventyayInitBatchSelection === 'function') {
        window.eventyayInitBatchSelection(resultsContainer);
    }

    resultsContainer.dispatchEvent(new CustomEvent('eventyay:ajax-results-replaced', {
        bubbles: true,
        detail: {
            container: resultsContainer,
        },
    }));
};

const updateNextInputs = function(url, tabId) {
    const normalizedUrl = new URL(url, window.location.href);
    const nextValue = normalizedUrl.pathname + normalizedUrl.search;
    const root = tabId ? document.getElementById(tabId) : document;

    if (!root) {
        return;
    }

    root.querySelectorAll('input[name="next"]').forEach(function(input) {
        input.value = nextValue;
    });
};

const syncFilterBadge = function(oldContext, newContext) {
    if (!oldContext || !newContext) return;
    
    const toggle = oldContext.querySelector('[data-advanced-filter-toggle]');
    const newToggle = newContext.querySelector('[data-advanced-filter-toggle]');
    if (!toggle || !newToggle) return;
    toggle.setAttribute('aria-expanded', newToggle.getAttribute('aria-expanded'));

    const newCount = parseInt(newToggle.getAttribute('data-filter-count'), 10) || 0;
    toggle.setAttribute('data-filter-count', String(newCount));

    let badge = toggle.querySelector('[data-advanced-filter-count]');
    if (newCount > 0) {
        if (badge) {
            badge.textContent = String(newCount);
            badge.hidden = false;  
        } else {
            badge = document.createElement('span');
            badge.className = 'badge advanced-filter-badge';
            badge.setAttribute('data-advanced-filter-count', '');
            badge.textContent = String(newCount);
            toggle.appendChild(badge);
        }
    } else if (badge) {
        badge.hidden = true;
        badge.remove();
    }
};

/* Result counts and links that carry the current filters are rendered from the
 * query string, so any of them sitting outside the results region would keep the
 * values of the last full page load. Templates mark those elements to have them
 * taken from the fetched document as well. */
const syncMarkedRegions = function(oldContext, newContext) {
    if (!oldContext || !newContext) return;

    const replacements = new Map();
    newContext.querySelectorAll('[data-ajax-sync]').forEach(function(element) {
        replacements.set(element.getAttribute('data-ajax-sync'), element);
    });

    oldContext.querySelectorAll('[data-ajax-sync]').forEach(function(stale) {
        const fresh = replacements.get(stale.getAttribute('data-ajax-sync'));
        if (fresh) {
            stale.replaceWith(fresh);
        }
    });
};

const fetchAndReplace = async function(url, replaceUrlParams, form) {
    const tabContext = getTabContextFromForm(form);
    let resultsContainer = getResultsContainer(tabContext.context);
    let requestController = null;
    if (!resultsContainer) {
        window.location.href = url;
        return;
    }

    resultsContainer.style.opacity = '0.5';

    try {
        if (activeRequestController) {
            activeRequestController.abort();
        }

        requestController = new AbortController();
        activeRequestController = requestController;

        const response = await fetch(url, {
            method: 'GET',
            credentials: 'same-origin',
            signal: requestController.signal,
        });

        if (activeRequestController !== requestController) {
            return;
        }

        if (!response.ok) {
            throw new Error('Unexpected response status: ' + response.status);
        }

        const data = await response.text();
        const doc = new DOMParser().parseFromString(data, 'text/html');
        const newContext = tabContext.tabId ? doc.getElementById(tabContext.tabId) : doc;
        const newResultsContainer = newContext ? getResultsContainer(newContext) : null;

        if (!newResultsContainer) {
            window.location.href = url;
            return;
        }

        resultsContainer.replaceWith(newResultsContainer);
        resultsContainer = newResultsContainer;
        resultsContainer.style.opacity = '1';

        syncFilterBadge(tabContext.context, newContext); 
        syncMarkedRegions(tabContext.context, newContext);

        reinitializeBehaviors(resultsContainer);

        if (replaceUrlParams) {
            history.pushState({}, '', url);
        }

        updateNextInputs(url, tabContext.tabId);
    } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
            resultsContainer.style.opacity = '1';
            return;
        }

        console.error('AJAX filter update failed', {
            url: url,
            error: error,
        });
        window.location.href = url;
    } finally {
        if (requestController && activeRequestController === requestController) {
            activeRequestController = null;
        }
    }
};

const buildFormUrl = function(form) {
    const url = form.getAttribute('action') || window.location.pathname;
    const query = new URLSearchParams(new FormData(form)).toString();
    if (!query) {
        return url;
    }

    return url + (url.includes('?') ? '&' : '?') + query;
};

const handleSubmit = function(event) {
    const form = event.target.closest('form');
    if (!form || !isFilterForm(form)) {
        return;
    }

    if (event.submitter && event.submitter.getAttribute('formaction')) {
        return;
    }

    event.preventDefault();
    fetchAndReplace(buildFormUrl(form), true, form);
};

const handleClearFilter = function(event) {
    const clearButton = event.target.closest('.btn-clear-filter');
    if (!clearButton) {
        return;
    }

    const form = clearButton.closest('form');
    if (!form || !isFilterForm(form)) {
        return;
    }

    const url = clearButton.getAttribute('href');
    if (!url) {
        return;
    }

    event.preventDefault();

    form.querySelectorAll('input[type="text"], input[type="search"]').forEach(function(input) {
        input.value = '';
    });

    form.querySelectorAll('select').forEach(function(select) {
        select.value = '';
        select.dispatchEvent(new Event('change', {
            bubbles: true,
        }));
    });

    fetchAndReplace(url, true, form);
};

const handlePaginationClick = function(event) {
    const paginationLink = event.target.closest('.pagination-container a, .pagination a');
    if (!paginationLink) {
        return;
    }

    const url = paginationLink.getAttribute('href');
    if (!url || url === '#') {
        return;
    }

    event.preventDefault();

    const tabPane = paginationLink.closest('.tab-pane');
    const formInTab = tabPane ? tabPane.querySelector('form') : null;
    const defaultForm = getFilterForms()[0] || null;
    fetchAndReplace(url, true, formInTab || tabPane || defaultForm);
};

const handleSortClick = function(event) {
    const sortLink = event.target.closest('thead a[href]');
    if (!sortLink) {
        return;
    }

    const url = sortLink.getAttribute('href');
    if (!url || !url.startsWith('?')) {
        return;
    }

    event.preventDefault();

    const tabPane = sortLink.closest('.tab-pane');
    const formInTab = tabPane ? tabPane.querySelector('form') : null;
    const defaultForm = getFilterForms()[0] || null;
    fetchAndReplace(url, true, formInTab || tabPane || defaultForm);
};

const setActiveTabUI = function(tabId) {
    if (!tabId) return;

    // Update the nav-tabs active state
    document.querySelectorAll('.nav-tabs a').forEach(function(link) {
        const href = link.getAttribute('href');
        if (!href) return;
        
        const linkUrl = new URL(href, window.location.href);
        const linkTab = linkUrl.searchParams.get('tab');
        const li = link.closest('li');
        if (li) {
            if (linkTab === tabId) {
                li.classList.add('active');
            } else {
                li.classList.remove('active');
            }
        }
    });

    // Update the tab-panes active state
    document.querySelectorAll('.tab-pane').forEach(function(pane) {
        if (pane.id === tabId) {
            pane.classList.add('active');
        } else {
            pane.classList.remove('active');
        }
    });
};

const handleTabClick = function(event) {
    const tabLink = event.target.closest('.nav-tabs a');
    if (!tabLink) {
        return;
    }

    const url = tabLink.getAttribute('href');
    if (!url || url.startsWith('#')) {
        // Local Bootstrap tab, let Bootstrap handle it
        return;
    }

    const urlObj = new URL(url, window.location.href);
    const tabParam = urlObj.searchParams.get('tab');
    if (!tabParam) {
        return;
    }

    event.preventDefault();

    setActiveTabUI(tabParam);

    const activeTab = document.getElementById(tabParam);
    const targetElement = (activeTab && activeTab.querySelector('form')) || activeTab || null;

    fetchAndReplace(url, true, targetElement);
};

const handlePopState = function() {
    const url = new URL(window.location.href, window.location.origin);
    const tabParam = url.searchParams.get('tab');
    if (tabParam) {
        setActiveTabUI(tabParam);
    }
    const tabPane = tabParam ? document.getElementById(tabParam) : null;
    const activeTab = tabPane || document.querySelector('.tab-pane.active');
    const targetElement = (activeTab && activeTab.querySelector('form')) || activeTab || getFilterForms()[0] || null;

    fetchAndReplace(window.location.href, false, targetElement);
};

const initAjaxFilter = function() {
    if (!getFilterForms().length && !hasAjaxResultsRegion()) {
        return;
    }

    document.addEventListener('submit', handleSubmit);
    document.addEventListener('click', handleClearFilter);
    document.addEventListener('click', handlePaginationClick);
    document.addEventListener('click', handleSortClick);
    document.addEventListener('click', handleTabClick);
    window.addEventListener('popstate', handlePopState);
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAjaxFilter);
} else {
    initAjaxFilter();
}

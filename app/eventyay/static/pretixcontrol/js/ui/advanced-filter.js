/**
 * Toggle the advanced filters panel on the list pages.
 */
function setExpanded(root, expanded) {
    const toggle = root.querySelector('[data-advanced-filter-toggle]');
    const panel = root.querySelector('[data-advanced-filter-advanced]');

    if (!toggle || !panel) {
        return;
    }

    toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    panel.hidden = !expanded;
    panel.classList.toggle('is-collapsed', !expanded);
}

function initAdvancedFilter(root = document) {
    const searchRoots = root.querySelectorAll('[data-advanced-filter-search]');
    searchRoots.forEach((searchRoot) => {
        const toggle = searchRoot.querySelector('[data-advanced-filter-toggle]');
        if (!toggle || toggle.dataset.advancedFilterBound === '1') {
            return;
        }
        toggle.dataset.advancedFilterBound = '1';

        toggle.addEventListener('click', () => {
            const expanded = toggle.getAttribute('aria-expanded') === 'true';
            setExpanded(searchRoot, !expanded);
        });
    });
}

function initOrganizerAutoSubmit(root = document) {
    if (typeof $ !== 'undefined') {
        $(root).find('#id_organizer').on('change', function() {
            $(this).closest('form').submit();
        });
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        initAdvancedFilter();
        initOrganizerAutoSubmit();
    });
} else {
    initAdvancedFilter();
    initOrganizerAutoSubmit();
}

/* Redirect legacy business-tab and ticketing-tab hashes to their dedicated pages.
 *
 * The <script> tag loading this file can carry data-business-redirect-url
 * and data-ticketing-redirect-url attributes.
 * This runs at parse time so the redirect happens before the page renders. */
{
    const scriptEl = document.currentScript;
    const businessRedirectUrl = scriptEl && scriptEl.getAttribute('data-business-redirect-url');
    const ticketingRedirectUrl = scriptEl && scriptEl.getAttribute('data-ticketing-redirect-url');
    if (location.hash) {
        const businessTabs = [
            '#tab-organizer_billing', '#tab-organizer_billing-open',
            '#tab-ticket_fee', '#tab-ticket_fee-open',
            '#tab-billing_validation', '#tab-billing_validation-open',
        ];
        if (businessRedirectUrl && businessTabs.indexOf(location.hash) !== -1) {
            window.location.replace(businessRedirectUrl + location.hash);
        }

        const ticketingTabs = [
            '#tab-payment_gateways', '#tab-payment_gateways-open',
            '#tab-payment-gateways', '#tab-payment-gateways-open',
            '#tab-cart', '#tab-cart-open',
        ];
        if (ticketingRedirectUrl && ticketingTabs.indexOf(location.hash) !== -1) {
            const targetHash = location.hash.replace(/_/g, '-');
            window.location.replace(ticketingRedirectUrl + targetHash);
        }
    }
}

/* Real-time synchronization of page content fields with page_locales language selector. */

(() => {
    function getSelectedLocales() {
        const checkboxes = document.querySelectorAll('input[type="checkbox"][name="page_locales"]:checked');
        const selected = Array.from(checkboxes).map((cb) => cb.value.toLowerCase());
        return selected.length > 0 ? selected : ['en'];
    }

    function syncTextareaVisibility() {
        const selected = getSelectedLocales();
        const wrappers = document.querySelectorAll('.i18n-textarea-wrapper[data-lang]');

        wrappers.forEach((wrapper) => {
            const lang = (wrapper.getAttribute('data-lang') || '').toLowerCase();
            const isVisible = selected.includes(lang);

            wrapper.style.display = isVisible ? '' : 'none';
            if (isVisible) {
                wrapper.removeAttribute('hidden');
            } else {
                wrapper.setAttribute('hidden', '');
            }
        });
    }

    function init() {
        syncTextareaVisibility();

        // Listen for checkbox changes on page_locales
        document.addEventListener('change', (e) => {
            if (e.target && e.target.name === 'page_locales') {
                syncTextareaVisibility();
            }
        });

        // Handle clicks on language grid badges, cells, and toolbar buttons
        document.addEventListener('click', (e) => {
            if (e.target && e.target.closest('.language-grid-widget')) {
                setTimeout(syncTextareaVisibility, 50);
            }
        });

        // Handle Bootstrap tab changes
        document.addEventListener('shown.bs.tab', syncTextareaVisibility);

        // MutationObserver for dynamic language grid updates
        const gridWidget = document.querySelector('.language-grid-widget');
        if (gridWidget && window.MutationObserver) {
            const observer = new MutationObserver(() => syncTextareaVisibility());
            observer.observe(gridWidget, { subtree: true, attributes: true, attributeFilter: ['checked', 'class'] });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    window.addEventListener('eventyay:toastui-ready', syncTextareaVisibility);
    window.addEventListener('load', syncTextareaVisibility);
})();

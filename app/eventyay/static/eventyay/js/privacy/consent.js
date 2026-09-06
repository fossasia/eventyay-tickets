/*
 * Bootstraps the Klaro consent manager from the admin-managed configuration.
 *
 * Klaro itself is vendored under static/klaro/ and loaded as a UMD bundle, so
 * it is available here as `window.klaro`. The configuration is read from a JSON
 * script tag rather than an inline script, which keeps the page free of inline
 * JavaScript and compatible with a strict CSP.
 */
const configElement = document.getElementById('klaro-config');
const klaro = window.klaro;

if (configElement && klaro) {
    const config = JSON.parse(configElement.textContent);

    // Klaro reads the config off window when it renders the banner.
    window.klaroConfig = config;
    klaro.setup(config);

    // Footer "Privacy settings" entry point, and the button inside every
    // blocked-embed placeholder.
    document.querySelectorAll('[data-privacy-settings]').forEach((trigger) => {
        trigger.addEventListener('click', (event) => {
            event.preventDefault();
            klaro.show(config);
        });
    });

    // Contextual consent: the wrapper stays in the DOM for the life of the page
    // so that accepting a category builds the embed and withdrawing it again
    // tears the embed back down.
    const manager = klaro.getManager(config);

    const buildEmbed = (wrapper) => {
        const iframe = document.createElement('iframe');
        iframe.src = wrapper.dataset.consentSrc;
        iframe.title = wrapper.dataset.consentTitle || '';
        iframe.loading = 'lazy';
        iframe.allowFullscreen = true;
        return iframe;
    };

    const syncConsentedEmbeds = () => {
        document.querySelectorAll('[data-consent-embed]').forEach((wrapper) => {
            const placeholder = wrapper.querySelector('[data-consent-placeholder]');
            const iframe = wrapper.querySelector('iframe');
            const consented = manager.getConsent(wrapper.dataset.consentEmbed);

            if (consented && !iframe) {
                wrapper.appendChild(buildEmbed(wrapper));
                if (placeholder) {
                    placeholder.hidden = true;
                }
            } else if (!consented && iframe) {
                // Withdrawal: drop the frame so the third party stops loading.
                iframe.remove();
                if (placeholder) {
                    placeholder.hidden = false;
                }
            }
        });
    };

    manager.watch({ update: syncConsentedEmbeds });
    syncConsentedEmbeds();
}

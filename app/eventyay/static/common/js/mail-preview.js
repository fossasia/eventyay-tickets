const initMailPreview = () => {
    const previewButtons = document.querySelectorAll('button[name="action"][value="preview"]');

    previewButtons.forEach(button => {
        let currentAbortController = null;

        button.addEventListener("click", async (e) => {
            e.preventDefault();
            e.stopImmediatePropagation();
            e.stopPropagation();

            const form = button.closest("form");
            const previewContainer = document.querySelector("#ajax-preview-container");

            if (!form || !previewContainer) {
                return;
            }

            if (currentAbortController) {
                currentAbortController.abort();
            }
            currentAbortController = new AbortController();
            const { signal } = currentAbortController;

            const setHTML = (container, htmlString) => {
                const fragment = document.createRange().createContextualFragment(htmlString);
                container.replaceChildren(fragment);
            };

            // Show loading state
            setHTML(previewContainer, `
                <fieldset class="mt-4 mb-4">
                    <legend id="preview">${typeof window.gettext === 'function' ? window.gettext("Email preview") : "Email preview"}</legend>
                    <div class="alert alert-info">
                        <div>
                            <i class="fa fa-spinner fa-spin mr-2"></i>
                            ${typeof window.gettext === 'function' ? window.gettext("Generating preview…") : "Generating preview…"}
                        </div>
                    </div>
                </fieldset>
            `);

            // Prepare form data
            const formData = new FormData(form);
            formData.append("action", "preview");

            // Remove loading state on the button that may be added by eventyay's form submit handler
            setTimeout(() => {
                button.disabled = false;
                button.classList.remove("loading", "disabled");
            }, 10);

            try {
                // Use getAttribute to avoid shadowing by inputs named "action"
                const actionUrl = form.getAttribute("action") || window.location.href;
                const method = form.getAttribute("method") || "POST";

                const response = await fetch(actionUrl, {
                    method: method,
                    body: formData,
                    headers: {
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    credentials: "same-origin",
                    signal: signal,
                });

                if (!response.ok) {
                    if (response.status === 400) {
                        // handled by parsing data if it contains error
                    } else {
                        throw new Error(`Preview request failed: ${response.status}`);
                    }
                }

                const data = await response.json();

                if (data.html) {
                    setHTML(previewContainer, data.html);
                } else if (data.error) {
                    let errorMessage = typeof window.gettext === 'function' ? window.gettext("Form validation failed.") : "Form validation failed.";
                    if (data.errors) {
                        const errorDetails = Object.entries(data.errors)
                            .map(([field, errors]) => {
                                const msgs = Array.isArray(errors) ? errors.map(e => e.message || e).join(', ') : errors;
                                return `<strong>${field}</strong>: ${msgs}`;
                            })
                            .join('<br>');
                        errorMessage += `<br><br>${errorDetails}`;
                    }
                    const err = new Error("Form validation failed.");
                    err.details = errorMessage;
                    throw err;
                } else {
                    throw new Error("Preview response did not contain HTML.");
                }
            } catch (error) {
                if (error.name === 'AbortError') {
                    return;
                }
                console.error("Email preview failed:", error);
                
                let errorHtml = typeof window.gettext === 'function' ? window.gettext("Email preview could not be generated. Please check the message content and try again.") : "Email preview could not be generated. Please check the message content and try again.";
                if (error.details) {
                    errorHtml = error.details;
                }

                setHTML(previewContainer, `
                    <fieldset class="mt-4 mb-4">
                        <legend id="preview">${typeof window.gettext === 'function' ? window.gettext("Email preview") : "Email preview"}</legend>
                        <div class="alert alert-danger">
                            <div>
                                ${errorHtml}
                            </div>
                        </div>
                    </fieldset>
                `);
            }
        });
    });
};

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initMailPreview);
} else {
    initMailPreview();
}

(function () {
    function getCsrfToken(table) {
        if (table && table.dataset.csrfToken) {
            return table.dataset.csrfToken;
        }
        const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (csrfInput && csrfInput.value) {
            return csrfInput.value;
        }
        const cookie = document.cookie.split("; ").find(row => row.startsWith("csrftoken="));
        return cookie ? decodeURIComponent(cookie.split("=")[1]) : "";
    }

    function updateStatus(row, active, statusText) {
        row.classList.toggle("deleted", !active);
        const toggle = row.querySelector(".video-server-toggle");
        if (toggle) {
            toggle.setAttribute("title", active ? "Active" : "Inactive");
        }
        const statusContainer = row.querySelector("[data-video-server-status], .video-server-status");
        if (!statusContainer) {
            return;
        }
        const badge = statusContainer.querySelector(".video-status-badge") || statusContainer;
        badge.classList.toggle("badge-active", active);
        badge.classList.toggle("badge-inactive", !active);
        badge.classList.toggle("label-success", active);
        badge.classList.toggle("label-default", !active);
        const icon = badge.querySelector(".fa");
        if (icon) {
            icon.className = active ? "fa fa-check" : "fa fa-minus";
        }
        const textNode = Array.from(badge.childNodes).find(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim());
        if (textNode) {
            textNode.textContent = " " + statusText;
        } else if (!icon) {
            badge.textContent = statusText;
        }
    }

    async function toggleServer(input) {
        const row = input.closest("[data-video-server-row]") || input.closest("tr");
        const table = input.closest("[data-video-server-table]") || input.closest(".table-responsive") || input.closest("table");
        const previous = !input.checked;
        input.disabled = true;
        if (row) {
            row.classList.add("video-server-row-saving");
        }

        const toggleUrl = input.dataset.toggleUrl || input.dataset.url;
        if (!toggleUrl) {
            input.disabled = false;
            return;
        }

        try {
            const response = await fetch(toggleUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrfToken(table),
                },
                body: JSON.stringify({ active: input.checked }),
            });
            let payload = {};
            try {
                payload = await response.json();
            } catch (error) {
                if (!response.ok) {
                    throw new Error("Could not update the video server.");
                }
                throw error;
            }
            if (!response.ok || !payload.ok) {
                throw new Error(payload.error || "Could not update the video server.");
            }
            input.checked = payload.active;
            if (row) {
                updateStatus(row, payload.active, payload.status);
            }
        } catch (error) {
            input.checked = previous;
            window.alert(error.message);
        } finally {
            if (row) {
                row.classList.remove("video-server-row-saving");
            }
            input.disabled = false;
        }
    }

    async function toggleProvider(input) {
        const container = input.closest("[data-provider-table]") || input.closest("table");
        const toggleUrl = container ? container.dataset.toggleUrl : null;
        if (!toggleUrl) return;

        const previous = !input.checked;
        input.disabled = true;
        const parentDiv = input.closest("td");
        const statusLabel = parentDiv ? parentDiv.querySelector(".toggle-status-label") : null;
        const toggle = input.closest(".video-server-toggle");

        try {
            const response = await fetch(toggleUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrfToken(container),
                },
                body: JSON.stringify({
                    provider: input.dataset.provider,
                    enabled: input.checked,
                }),
            });
            let payload = {};
            try {
                payload = await response.json();
            } catch (err) {
                if (!response.ok) throw new Error("Could not update video provider settings.");
                throw err;
            }
            if (!response.ok || !payload.ok) {
                throw new Error(payload.error || "Could not update video provider settings.");
            }
            input.checked = payload.enabled;
            if (statusLabel) {
                statusLabel.innerHTML = payload.enabled
                    ? '<span class="text-success"><span class="fa fa-check"></span> Enabled</span>'
                    : '<span class="text-danger"><span class="fa fa-ban"></span> Disabled</span>';
                if (toggle) toggle.setAttribute("title", payload.enabled ? "Enabled" : "Disabled");
            }
        } catch (error) {
            input.checked = previous;
            window.alert(error.message);
        } finally {
            input.disabled = false;
        }
    }

    document.addEventListener("change", (event) => {
        const providerInput = event.target.closest(".video-provider-visibility-toggle");
        if (providerInput) {
            toggleProvider(providerInput);
            return;
        }
        const input = event.target.closest("[data-video-server-toggle], .video-server-toggle-input");
        if (!input) {
            return;
        }
        toggleServer(input);
    });
}());


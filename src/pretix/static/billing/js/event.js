document.getElementById("back-btn").addEventListener("click", function () {
    const basePath = JSON.parse(document.getElementById('base_path').textContent);
    const url = window.location.href
    const organizerMatch = url.match(/organizer\/([^/]+)/);
    const organizerSlug = organizerMatch ? organizerMatch[1] : null;
    window.location.href = `${basePath}/control/organizer/${organizerSlug}/settings/billing`;
});

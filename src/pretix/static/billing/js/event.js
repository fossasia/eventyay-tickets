const basePath = JSON.parse(document.getElementById('base_path').textContent);
document.getElementById("back-btn").addEventListener("click", function () {
    const url = window.location.href
    const organizerMatch = url.match(/organizer\/([^/]+)/);
    const organizerSlug = organizerMatch ? organizerMatch[1] : null;
    console.log(organizerSlug);
    window.location.href = `${basePath}/control/organizer/${organizerSlug}/settings/billing`;
});
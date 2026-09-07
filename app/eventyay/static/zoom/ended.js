/**
 * Eventyay Zoom Meeting Ended Handler
 * Notifies parent frame to return to the attendee dashboard.
 */

export function returnToDashboard() {
    if (window.parent && window.parent !== window) {
        window.parent.postMessage({ event: 'zoom:leave', action: 'leave' }, '*');
    }
    try {
        if (window.top && window.top !== window) {
            window.top.location.href = '/about';
            return;
        }
    } catch (e) {
        console.warn('Unable to navigate window.top:', e);
    }
    try {
        if (window.parent && window.parent !== window) {
            window.parent.location.href = '/about';
            return;
        }
    } catch (e) {
        console.warn('Unable to navigate window.parent:', e);
    }
    window.location.href = '/about';
}

document.addEventListener('DOMContentLoaded', () => {
    const returnBtn = document.getElementById('btn-return-dashboard');
    if (returnBtn) {
        returnBtn.addEventListener('click', (e) => {
            e.preventDefault();
            returnToDashboard();
        });
    }
    // Automatically return to attendee dashboard
    returnToDashboard();
});

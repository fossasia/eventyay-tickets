/**
 * Eventyay Zoom Meeting Integration
 * ES Module controlling embedded Zoom client, SDK lifecycle, topbar actions, and toast messaging.
 */

let toastTimeoutId = null;

export function showToast() {
    const toast = document.getElementById('copy-toast');
    if (!toast) return;
    toast.classList.add('show');
    if (toastTimeoutId) {
        clearTimeout(toastTimeoutId);
    }
    toastTimeoutId = setTimeout(() => {
        toast.classList.remove('show');
    }, 2000);
}

export async function copyToClipboard(text) {
    if (!text) return;
    try {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
            showToast();
            return;
        }
    } catch (err) {
        console.warn('navigator.clipboard failed, falling back to document.execCommand:', err);
    }

    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.select();
    try {
        document.execCommand('copy');
        showToast();
    } catch (execErr) {
        console.error('Failed to copy text using execCommand:', execErr);
    } finally {
        document.body.removeChild(textarea);
    }
}

export function showFallbackEmbed(fallbackUrl) {
    const root = document.getElementById('zmmtg-root');
    if (root) {
        root.style.display = 'none';
    }
    const frame = document.getElementById('zoom-embedded-frame');
    if (frame) {
        frame.style.display = 'block';
        if (fallbackUrl && (!frame.src || frame.src === 'about:blank')) {
            frame.src = fallbackUrl;
        }
    }
}

export function leaveMeeting() {
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

export function initZoomSdk(config) {
    if (typeof ZoomMtg === 'undefined') {
        console.warn('ZoomMtg SDK failed to load from CDN. Showing embedded fallback.');
        showFallbackEmbed(config.zoomWebUrl);
        return;
    }

    try {
        ZoomMtg.setZoomJSLib('https://source.zoom.us/3.11.2/lib', '/av');
        ZoomMtg.preLoadWasm();
        ZoomMtg.prepareWebSDK();

        if (config.langUrl) {
            ZoomMtg.i18n.load(config.langUrl, config.lang || 'en-US');
            ZoomMtg.i18n.reload(config.langUrl, config.lang || 'en-US');
        } else {
            ZoomMtg.i18n.load(config.lang || 'en-US');
            ZoomMtg.i18n.reload(config.lang || 'en-US');
        }

        ZoomMtg.init({
            debug: Boolean(config.debug),
            leaveUrl: config.leaveUrl || '/zoom/ended/',
            isSupportAV: true,
            isSupportChat: Boolean(config.supportChat),
            showMeetingHeader: false,
            disableInvite: true,
            disableCallOut: true,
            meetingInfo: ['topic', 'host', 'telPwd', 'participant', 'dc', 'enctype', 'report'],
            success: function () {
                ZoomMtg.join({
                    signature: config.signature,
                    sdkKey: config.apiKey,
                    meetingNumber: config.meetingNumber,
                    userName: config.userName,
                    userEmail: config.userEmail,
                    passWord: config.password,
                    error: function (err) {
                        console.error('ZoomMtg.join error:', err);
                        showFallbackEmbed(config.zoomWebUrl);
                    }
                });
            },
            error: function (err) {
                console.error('ZoomMtg.init error:', err);
                showFallbackEmbed(config.zoomWebUrl);
            }
        });
    } catch (e) {
        console.error('Exception during Zoom SDK initialization:', e);
        showFallbackEmbed(config.zoomWebUrl);
    }
}

function parseConfig() {
    const configElem = document.getElementById('zoom-config');
    if (!configElem) return {};
    try {
        return JSON.parse(configElem.textContent || '{}');
    } catch (e) {
        console.error('Failed to parse zoom-config JSON:', e);
        return {};
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const config = parseConfig();

    const leaveBtn = document.getElementById('btn-leave-meeting');
    if (leaveBtn) {
        leaveBtn.addEventListener('click', (e) => {
            e.preventDefault();
            leaveMeeting();
        });
    }

    const copyButtons = document.querySelectorAll('.chip-copy-btn');
    copyButtons.forEach((btn) => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const textToCopy = btn.getAttribute('data-copy');
            if (textToCopy) {
                copyToClipboard(textToCopy);
            }
        });
    });

    if (config.hasSdkCredentials) {
        initZoomSdk(config);
    }
});

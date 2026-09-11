/**
 * Returns true when `ip` is a private, loopback, or link-local IPv4 address.
 *
 * Ranges covered:
 *   10.0.0.0/8        — Class A private
 *   172.16.0.0/12     — Class B private
 *   192.168.0.0/16    — Class C private
 *   127.0.0.0/8       — Loopback
 *   169.254.0.0/16    — Link-local (APIPA)
 *
 * @param {string} ip
 * @returns {boolean}
 */
export function isPrivateOrLocalIP(ip) {
	if (!/^(\d{1,3}\.){3}\d{1,3}$/.test(ip)) return false;
	const parts = ip.split('.').map(Number);
	if (!parts.every(octet => octet <= 255)) return false;
	return parts[0] === 10 ||
	       (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31) ||
	       (parts[0] === 192 && parts[1] === 168) ||
	       parts[0] === 127 ||
	       (parts[0] === 169 && parts[1] === 254);
}

/**
 * Rewrites private/local IPv4 addresses in an SDP answer so that ICE
 * candidates and connection-data lines point to `replacementHost` instead.
 *
 * This is only needed in local-dev environments where the media server
 * (e.g. MediaMTX inside Docker) advertises an internal container IP that the
 * browser cannot reach.  In production the server should be configured to
 * advertise its public address directly (e.g. via webrtcAdditionalHosts in
 * mediamtx.yml) so this function becomes a no-op.
 *
 * @param {string} sdp              — Raw SDP answer string received from the WHEP endpoint
 * @param {string} replacementHost  — Hostname/IP to substitute (typically window.location.hostname)
 * @returns {string}                — SDP with private IPs replaced; unchanged when replacementHost
 *                                    is not itself a private IP
 */
export function rewritePrivateIPsInSdp(sdp, replacementHost) {
	if (!isPrivateOrLocalIP(replacementHost)) return sdp;

	return sdp.replace(/(c=IN IP4 |a=candidate:(?:[^ ]+ ){4})([0-9.]+)/g, (match, prefix, ip) => {
		return isPrivateOrLocalIP(ip) ? prefix + replacementHost : match;
	});
}

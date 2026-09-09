let nativeRTCPeerConnection = null;

function getNativeRTCPeerConnection() {
	if (nativeRTCPeerConnection) return nativeRTCPeerConnection;
	
	const iframe = document.createElement('iframe')
	iframe.style.display = 'none'
	document.body.appendChild(iframe)
	nativeRTCPeerConnection = iframe.contentWindow.RTCPeerConnection || window.RTCPeerConnection
	// Intentionally leaving iframe attached as Chrome prevents creating RTCPeerConnection in detached documents
	return nativeRTCPeerConnection
}

export class WhepClient {
	constructor(url, audioElement) {
		this.url = url
		this.audioElement = audioElement
		this.abortController = new AbortController()
		
		const PeerConnectionClass = getNativeRTCPeerConnection()
		this.peerConnection = new PeerConnectionClass()

		this.peerConnection.ontrack = (event) => {
			if (this.audioElement && this.audioElement.srcObject !== event.streams[0]) {
				this.audioElement.srcObject = event.streams[0]
				this.audioElement.play().catch(e => console.warn('WHEP audio play failed:', e))
			}
		}

		this.peerConnection.addTransceiver('audio', { direction: 'recvonly' })
	}

	async connect() {
		try {
			const offer = await this.peerConnection.createOffer()
			await this.peerConnection.setLocalDescription(offer)

			// Wait for ICE gathering before sending the SDP
			await new Promise((resolve, reject) => {
				const abortError = new Error('Aborted');
				abortError.name = 'AbortError';
				
				if (this.abortController.signal.aborted) {
					reject(abortError);
					return;
				}
				if (this.peerConnection.iceGatheringState === 'complete') {
					resolve();
					return;
				}
				
				let timeoutId;
				
				const cleanup = () => {
					if (this.peerConnection) {
						this.peerConnection.removeEventListener('icegatheringstatechange', handler);
					}
					this.abortController.signal.removeEventListener('abort', abortHandler);
					clearTimeout(timeoutId);
				};
				
				const handler = () => {
					if (this.peerConnection.iceGatheringState === 'complete') {
						cleanup();
						resolve();
					}
				};
				
				const abortHandler = () => {
					cleanup();
					reject(abortError);
				};
				
				this.peerConnection.addEventListener('icegatheringstatechange', handler);
				this.abortController.signal.addEventListener('abort', abortHandler, { once: true });
				
				timeoutId = setTimeout(() => {
					cleanup();
					resolve();
				}, 500);
			});

			const response = await fetch(this.url, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/sdp'
				},
				body: this.peerConnection.localDescription.sdp,
				signal: this.abortController.signal
			})

			if (!response.ok) {
				throw new Error(`WHEP endpoint returned ${response.status}`)
			}

			const originalAnswerSdp = await response.text();
			// Force the IP to the browser's hostname when it is a valid private/local IPv4 address (for local dev)
			const hostname = window.location.hostname;
			
			const isPrivateOrLocalIP = (ip) => {
				if (!/^(\d{1,3}\.){3}\d{1,3}$/.test(ip)) return false;
				const parts = ip.split('.').map(Number);
				if (!parts.every(octet => octet <= 255)) return false;
				return parts[0] === 10 || 
				       (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31) ||
				       (parts[0] === 192 && parts[1] === 168) ||
				       parts[0] === 127 ||
				       (parts[0] === 169 && parts[1] === 254);
			};

			const isPrivateIP = isPrivateOrLocalIP(hostname);
			
			const answerSdp = isPrivateIP 
				? originalAnswerSdp.replace(/(c=IN IP4 |a=candidate:(?:[^ ]+ ){4})([0-9.]+)/g, (match, prefix, ip) => {
					return isPrivateOrLocalIP(ip) ? prefix + hostname : match;
				}) 
				: originalAnswerSdp;

			if (this.abortController.signal.aborted || !this.peerConnection) return;

			await this.peerConnection.setRemoteDescription({
				type: 'answer',
				sdp: answerSdp
			})
		} catch (error) {
			if (error.name === 'AbortError') return;
			console.error('WHEP connection failed:', error)
			throw error
		}
	}

	disconnect() {
		if (this.abortController) {
			this.abortController.abort()
		}
		if (this.peerConnection) {
			this.peerConnection.close()
			this.peerConnection = null
		}
		if (this.audioElement) {
			this.audioElement.srcObject = null
		}
	}
}

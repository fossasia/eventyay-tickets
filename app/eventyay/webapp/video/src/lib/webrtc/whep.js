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
		
		const PeerConnectionClass = window.RTCPeerConnection
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
			await new Promise((resolve) => {
				if (this.peerConnection.iceGatheringState === 'complete') {
					resolve();
					return;
				}
				const timer = setTimeout(resolve, 500);
				const handler = () => {
					if (this.peerConnection.iceGatheringState === 'complete') {
						clearTimeout(timer);
						this.peerConnection.removeEventListener('icegatheringstatechange', handler);
						resolve();
					}
				};
				this.peerConnection.addEventListener('icegatheringstatechange', handler);
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
			// Force the IP to the browser's hostname to avoid Docker/WSL NAT issues
			const answerSdp = originalAnswerSdp.replace(/c=IN IP4 [0-9.]+/g, 'c=IN IP4 ' + window.location.hostname);

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

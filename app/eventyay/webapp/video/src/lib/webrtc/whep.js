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

			const answerSdp = await response.text()
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

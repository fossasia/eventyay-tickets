import { TtsParser } from './tts-parser';

/**
 * Manages WebSocket connection to Voxbento TTS endpoint and schedules audio playback
 */
export class AudioScheduler {
	constructor(wsUrl, audioElement) {
		this.wsUrl = wsUrl;
		this.audioElement = audioElement;
		this.ws = null;
		this.parser = new TtsParser();
		this.audioContext = null;
		this.audioBuffer = null;
		this.isConnected = false;
		this.retryCount = 0;
		this.maxRetries = 5;
		this.retryDelay = 1000; // exponential backoff starts at 1s
	}

	async connect() {
		if (this.isConnected) {
			console.warn('AudioScheduler already connected');
			return;
		}

		return new Promise((resolve, reject) => {
			try {
				this.ws = new WebSocket(this.wsUrl);
				this.ws.binaryType = 'arraybuffer';

				this.ws.onopen = () => {
					this.isConnected = true;
					this.retryCount = 0;
					console.log('AudioScheduler connected to TTS endpoint');
					resolve();
				};

				this.ws.onmessage = (event) => {
					this.handleMessage(event.data);
				};

				this.ws.onerror = (error) => {
					console.error('AudioScheduler WebSocket error:', error);
					this.handleError(error, reject);
				};

				this.ws.onclose = () => {
					this.handleClose();
				};
			} catch (error) {
				console.error('Failed to create WebSocket connection:', error);
				this.handleError(error, reject);
			}
		});
	}

	handleError(error, reject) {
		this.isConnected = false;
		if (reject) {
			reject(error);
		}
	}

	handleClose() {
		this.isConnected = false;
		if (this.retryCount < this.maxRetries) {
			const delay = this.retryDelay * Math.pow(2, this.retryCount);
			this.retryCount++;
			console.log(`Attempting to reconnect to TTS endpoint (attempt ${this.retryCount}/${this.maxRetries}) after ${delay}ms`);
			setTimeout(() => {
				this.connect().catch(error => {
					console.error('Reconnection failed:', error);
				});
			}, delay);
		} else {
			console.error('Max retries reached for TTS connection');
		}
	}

	handleMessage(data) {
		if (!(data instanceof ArrayBuffer)) {
			console.warn('Received non-binary TTS message');
			return;
		}

		this.parser.append(data);
		const frames = this.parser.getFrames();

		for (const frame of frames) {
			this.scheduleAudioFrame(frame);
		}
	}

	scheduleAudioFrame(frame) {
		if (!frame.audioData || frame.audioData.length === 0) {
			return;
		}

		// Initialize audio context if needed
		if (!this.audioContext) {
			try {
				const AudioContextClass = window.AudioContext || window.webkitAudioContext;
				this.audioContext = new AudioContextClass();
			} catch (error) {
				console.error('Failed to create AudioContext:', error);
				return;
			}
		}

		const audioData = new Float32Array(frame.audioData.length);
		for (let i = 0; i < frame.audioData.length; i++) {
			// Convert byte to float32 (-1 to 1 range)
			audioData[i] = (frame.audioData[i] - 128) / 128;
		}

		try {
			const audioBuffer = this.audioContext.createBuffer(
				1, // mono
				audioData.length,
				this.audioContext.sampleRate
			);
			audioBuffer.getChannelData(0).set(audioData);

			const source = this.audioContext.createBufferSource();
			source.buffer = audioBuffer;
			source.connect(this.audioContext.destination);
			source.start(this.audioContext.currentTime);
		} catch (error) {
			console.error('Error scheduling audio frame:', error);
		}
	}

	pause() {
		if (this.audioContext) {
			this.audioContext.suspend();
		}
	}

	resume() {
		if (this.audioContext && this.audioContext.state === 'suspended') {
			this.audioContext.resume().catch(error => {
				console.warn('Failed to resume AudioContext:', error);
			});
		}
	}

	disconnect() {
		this.isConnected = false;
		this.retryCount = this.maxRetries; // Prevent reconnection

		if (this.ws) {
			this.ws.close();
			this.ws = null;
		}

		if (this.audioContext) {
			try {
				this.audioContext.close();
			} catch (error) {
				console.warn('Error closing AudioContext:', error);
			}
			this.audioContext = null;
		}

		this.parser = new TtsParser();
		console.log('AudioScheduler disconnected');
	}
}

// Guards against a desynchronised or corrupt stream claiming an absurd frame size.
const MAX_FRAME_LENGTH = 16 * 1024 * 1024;

/**
 * Parses Voxbento binary frame format: [1-byte version][4-byte length][JSON header][audio bytes]
 */
export class TtsParser {
	constructor() {
		this.buffer = new Uint8Array(0);
		this.frames = [];
	}

	append(data) {
		const incoming = data instanceof Uint8Array ? data : new Uint8Array(data);
		const newBuffer = new Uint8Array(this.buffer.length + incoming.length);
		newBuffer.set(this.buffer);
		newBuffer.set(incoming, this.buffer.length);
		this.buffer = newBuffer;
		this.parseFrames();
	}

	parseFrames() {
		while (this.buffer.length >= 5) {
			const version = this.buffer[0];
			if (version !== 1) {
				console.warn(`Unexpected TTS frame version: ${version}`);
				this.buffer = this.buffer.slice(1);
				continue;
			}

			const lengthView = new DataView(this.buffer.buffer, this.buffer.byteOffset + 1, 4);
			const frameLength = lengthView.getUint32(0, false);

			if (frameLength > MAX_FRAME_LENGTH) {
				console.warn(`TTS frame length ${frameLength} exceeds ${MAX_FRAME_LENGTH}, resynchronising`);
				this.buffer = this.buffer.slice(1);
				continue;
			}

			const totalLength = 5 + frameLength;
			if (this.buffer.length < totalLength) {
				break;
			}

			try {
				const frame = this.parseFrame(totalLength);
				if (frame) {
					this.frames.push(frame);
				}
			} catch (error) {
				console.error('Error parsing TTS frame:', error);
			}

			this.buffer = this.buffer.slice(totalLength);
		}
	}

	parseFrame(totalLength) {
		const frameData = this.buffer.slice(0, totalLength);
		const headerEnd = this.findHeaderEnd(frameData, 5);

		if (headerEnd === -1) {
			console.warn('Could not find JSON header terminator in TTS frame');
			return null;
		}

		try {
			const headerJson = new TextDecoder().decode(frameData.slice(5, headerEnd));
			const header = JSON.parse(headerJson);
			const audioData = frameData.slice(headerEnd, totalLength);

			return {
				header,
				audioData
			};
		} catch (error) {
			console.error('Failed to parse TTS frame header:', error);
			return null;
		}
	}

	findHeaderEnd(data, startIndex) {
		let braceCount = 0;
		let inString = false;
		let escaped = false;

		for (let i = startIndex; i < data.length; i++) {
			const byte = data[i];
			const char = String.fromCharCode(byte);

			if (escaped) {
				escaped = false;
				continue;
			}

			if (char === '\\') {
				escaped = true;
				continue;
			}

			if (char === '"' && !escaped) {
				inString = !inString;
				continue;
			}

			if (!inString) {
				if (char === '{') {
					braceCount++;
				} else if (char === '}') {
					braceCount--;
					if (braceCount === 0) {
						return i + 1;
					}
				}
			}
		}

		return -1;
	}

	getFrames() {
		const result = this.frames;
		this.frames = [];
		return result;
	}
}

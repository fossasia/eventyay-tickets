/**
 * AudioScheduler teardown behaviour.
 * Run: node --test src/lib/audio-scheduler.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { AudioScheduler } from './audio-scheduler.js'

function encodeFrame(header, audio) {
	const headerBytes = new TextEncoder().encode(JSON.stringify(header))
	const body = new Uint8Array(headerBytes.length + audio.length)
	body.set(headerBytes)
	body.set(audio, headerBytes.length)
	const frame = new Uint8Array(5 + body.length)
	frame[0] = 1
	new DataView(frame.buffer).setUint32(1, body.length, false)
	frame.set(body, 5)
	return frame.buffer
}

let audioContextsCreated = 0
let sourcesStarted = 0

class FakeAudioContext {
	constructor() {
		audioContextsCreated++
		this.sampleRate = 48000
		this.currentTime = 0
		this.state = 'running'
		this.destination = {}
	}

	createBuffer(channels, length, sampleRate) {
		const channelData = new Float32Array(length)
		return {
			duration: length / sampleRate,
			getChannelData: () => channelData
		}
	}

	createBufferSource() {
		return {
			buffer: null,
			connect() {},
			start() {
				sourcesStarted++
			}
		}
	}

	close() {}
	suspend() {}
	resume() {
		return Promise.resolve()
	}
}

// The scheduler runs against browser globals, so stand them up for the duration
// of a test and put whatever was there back afterwards.
async function withBrowserStubs(run) {
	const sockets = []
	const originalWebSocket = globalThis.WebSocket
	const originalWindow = globalThis.window
	const originalConsole = { log: console.log, warn: console.warn, error: console.error }

	globalThis.WebSocket = class {
		constructor(url) {
			this.url = url
			sockets.push(this)
		}

		close() {
			if (this.onclose) this.onclose()
		}
	}
	globalThis.window = { AudioContext: FakeAudioContext }
	console.log = () => {}
	console.warn = () => {}
	console.error = () => {}
	audioContextsCreated = 0
	sourcesStarted = 0

	try {
		await run(sockets)
	} finally {
		globalThis.WebSocket = originalWebSocket
		if (originalWindow === undefined) {
			delete globalThis.window
		} else {
			globalThis.window = originalWindow
		}
		Object.assign(console, originalConsole)
	}
}

async function connectedScheduler(sockets) {
	const scheduler = new AudioScheduler('wss://voxbento.invalid/tts', null)
	const connecting = scheduler.connect()
	sockets[0].onopen()
	await connecting
	return scheduler
}

test('schedules audio for a frame received while connected', async () => {
	await withBrowserStubs(async (sockets) => {
		const scheduler = await connectedScheduler(sockets)

		sockets[0].onmessage({ data: encodeFrame({ seq: 1 }, new Uint8Array([1, 2, 3, 4])) })

		assert.equal(audioContextsCreated, 1)
		assert.equal(sourcesStarted, 1)
		scheduler.disconnect()
	})
})

test('drops a message that arrives after disconnect', async () => {
	await withBrowserStubs(async (sockets) => {
		const scheduler = await connectedScheduler(sockets)
		const socket = sockets[0]

		socket.onmessage({ data: encodeFrame({ seq: 1 }, new Uint8Array([1, 2, 3, 4])) })
		assert.equal(audioContextsCreated, 1)
		assert.equal(sourcesStarted, 1)

		scheduler.disconnect()

		// close() does not detach the handler, so a frame already in flight when the
		// listener switched languages still gets delivered to this callback.
		socket.onmessage({ data: encodeFrame({ seq: 2 }, new Uint8Array([5, 6, 7, 8])) })

		assert.equal(audioContextsCreated, 1, 'no AudioContext is recreated after teardown')
		assert.equal(sourcesStarted, 1, 'no audio is scheduled after teardown')
		assert.equal(scheduler.audioContext, null, 'teardown leaves no audio context behind')
		assert.equal(sockets.length, 1, 'no replacement socket is opened')
	})
})

test('retries a dropped connection on an exponential backoff', async (t) => {
	t.mock.timers.enable({ apis: ['setTimeout'] })
	await withBrowserStubs(async (sockets) => {
		const scheduler = await connectedScheduler(sockets)

		sockets[0].onclose()
		assert.equal(sockets.length, 1, 'the retry is deferred rather than immediate')

		t.mock.timers.tick(999)
		assert.equal(sockets.length, 1, 'nothing reconnects before the first delay elapses')
		t.mock.timers.tick(1)
		assert.equal(sockets.length, 2, 'the first retry reconnects after 1s')

		sockets[1].onclose()
		t.mock.timers.tick(1999)
		assert.equal(sockets.length, 2, 'the second delay is longer than the first')
		t.mock.timers.tick(1)
		assert.equal(sockets.length, 3, 'the second retry reconnects after 2s')

		scheduler.disconnect()
	})
})

test('gives up once the retry limit is reached', async (t) => {
	t.mock.timers.enable({ apis: ['setTimeout'] })
	await withBrowserStubs(async (sockets) => {
		const scheduler = await connectedScheduler(sockets)

		for (let attempt = 0; attempt < scheduler.maxRetries; attempt++) {
			sockets[sockets.length - 1].onclose()
			t.mock.timers.tick(scheduler.retryDelay * Math.pow(2, attempt))
		}
		assert.equal(sockets.length, scheduler.maxRetries + 1, 'the original socket plus one per retry')

		sockets[sockets.length - 1].onclose()
		t.mock.timers.tick(60000)
		assert.equal(sockets.length, scheduler.maxRetries + 1, 'no further sockets once the limit is reached')

		scheduler.disconnect()
	})
})

test('a successful reconnect resets the backoff', async (t) => {
	t.mock.timers.enable({ apis: ['setTimeout'] })
	await withBrowserStubs(async (sockets) => {
		const scheduler = await connectedScheduler(sockets)

		sockets[0].onclose()
		t.mock.timers.tick(scheduler.retryDelay)
		assert.equal(sockets.length, 2)
		sockets[1].onopen()
		assert.equal(scheduler.retryCount, 0, 'reconnecting clears the accumulated backoff')

		sockets[1].onclose()
		t.mock.timers.tick(scheduler.retryDelay)
		assert.equal(sockets.length, 3, 'the next drop retries at the base delay again')

		scheduler.disconnect()
	})
})

test('disconnect cancels a retry that is already pending', async (t) => {
	t.mock.timers.enable({ apis: ['setTimeout'] })
	await withBrowserStubs(async (sockets) => {
		const scheduler = await connectedScheduler(sockets)

		sockets[0].onclose()
		assert.notEqual(scheduler.reconnectTimer, null, 'a retry is pending')

		scheduler.disconnect()
		assert.equal(scheduler.reconnectTimer, null, 'the pending retry is cleared')

		t.mock.timers.tick(60000)
		assert.equal(sockets.length, 1, 'the cancelled retry never opens a socket')
	})
})

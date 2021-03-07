/* global WebSocket */
import EventEmitter from 'events'
import ApiError from './ApiError'

const defer = function () {
	const deferred = {}
	deferred.promise = new Promise(function (resolve, reject) {
		deferred.resolve = resolve
		deferred.reject = reject
	})
	return deferred
}

class WebSocketClient extends EventEmitter {
	constructor (url, config) {
		super()
		const defaultConfig = {
			pingInterval: 10000,
			joinTimeout: 60000,
			reconnectDelay: 1000,
			token: null,
			clientId: null
		}
		this._config = Object.assign(defaultConfig, config)
		this._url = url
	}

	connect () {
		this._createSocket()
	}

	close () {
		this._normalClose = true
		this._socket.close()
		clearTimeout(this._joinTimeout)
	}

	call (name, data, opts) {
		const options = {
			timeout: 15000
		}
		Object.assign(options, opts)
		const { id, promise } = this._createRequest()
		const payload = [
			name,
			id,
			data
		]
		this._send(JSON.stringify(payload))
		setTimeout(() => {
			if (this._openRequests[id]) {
				const timeoutedRequest = this._popPendingRequest(id)
				timeoutedRequest.deferred.reject(new Error('call timed out'))
			}
		}, options.timeout)
		return promise
	}

	// ===========================================================================
	// INTERNALS
	// ===========================================================================
	_createSocket () {
		this._socket = new WebSocket(this._url)
		this.socketState = 'connecting' // 'closed', 'open', 'connecting'
		this._pingState = {
			latestPong: 0
		}
		this.normalClose = false
		this._socket.addEventListener('open', () => {
			this.emit('open')
			this.socketState = 'open'
			this._authenticate()
			this._joinTimeout = setTimeout(() => {
				this._handlePingTimeout()
			}, this._config.joinTimeout)
		})

		this._socket.addEventListener('close', (event) => {
			this.socketState = 'closed'
			this.emit('closed', event.code)
			if (!this._normalClose) {
				setTimeout(() => {
					this.emit('reconnecting')
					this._createSocket()
				}, this._config.reconnectDelay)
			}
		})
		this._socket.addEventListener('message', this._processMessage.bind(this))
		this._openRequests = {} // save deferred promises from requests waiting for reponse
		this._nextRequestIndex = 1 // autoincremented message id
		this._joinTimeout = null
	}

	_send (payload) {
		this._socket.send(payload)
		this.emit('log', {
			direction: 'send',
			data: payload
		})
	}

	_authenticate () {
		const payload = {}
		if (this._config.token) {
			payload.token = this._config.token
		}
		if (this._config.clientId) {
			payload.client_id = this._config.clientId
		}
		this._send(JSON.stringify(['authenticate', payload]))
	}

	_ping (starterSocket) { // we need a ref to the socket to detect reconnects and stop the old ping loop
		if (this._socket.readyState !== 1) return
		const timestamp = Date.now()
		const payload = [
			'ping',
			timestamp
		]
		this._send(JSON.stringify(payload))
		this.emit('ping')
		setTimeout(() => {
			if (this._socket.readyState !== 1 || this._socket !== starterSocket) return // looping on old socket, abort
			if (timestamp > this._pingState.latestPong) // we received no pong after the last ping
				this._handlePingTimeout()
			else this._ping(starterSocket)
		}, this._config.pingInterval)
	}

	_handlePingTimeout () {
		this._socket.close()
		this.emit('closed')
	}

	_processMessage (rawMessage) {
		const message = JSON.parse(rawMessage.data)

		const actionHandlers = {
			error: this._handleError.bind(this),
			success: this._handleCallSuccess.bind(this),
			pong: this._handlePong.bind(this),
			'connection.reload': this._handleReload.bind(this),
			authenticated: this._handleJoined.bind(this)
		}
		if (actionHandlers[message[0]] === undefined) {
			this.emit('message', message)
		} else {
			actionHandlers[message[0]](message)
		}
		this.emit('log', {
			direction: 'receive',
			data: rawMessage.data
		})
	}

	// request - response promise matching
	_createRequest (callback) {
		const id = this._nextRequestIndex++
		const deferred = defer()
		this._openRequests[id] = { deferred, callback }
		return { id, promise: deferred.promise }
	}

	_popPendingRequest (id) {
		const req = this._openRequests[id]
		this._openRequests[id] = undefined
		return req
	}

	_handleError (message) {
		const req = this._popPendingRequest(message[1])
		if (req === null || req === undefined) {
			this.emit('error', message[message.length - 1])
		} else {
			req.deferred.reject(new ApiError(message[2]))
		}
	}

	_handleCallSuccess (message) {
		const req = this._popPendingRequest(message[1])
		if (req === null || req === undefined) {
			this.emit('warning', `no saved request with id: ${message[1]}`)
		} else {
			if (req.callback) {
				req.callback(message[2], req.deferred)
			} else {
				req.deferred.resolve(message[2])
			}
		}
	}

	_handleReload (message) {
		this.close()
		location.reload()
	}

	_handlePong (message) {
		this.emit('pong')
		this._pingState.latestPong = Date.now()
	}

	_handleJoined (message) {
		clearTimeout(this._joinTimeout)
		this._joinTimeout = null
		this.emit('joined', message[1])
		// start pinging
		const socket = this._socket
		setTimeout(() => {
			if (socket === this._socket) this._ping(socket)
		}, this._config.pingInterval)
	}

	_handleJoinError (message) {
		clearTimeout(this._joinTimeout)
		this._joinTimeout = null
		this.emit('error', message[1].error)
	}
}

export default WebSocketClient

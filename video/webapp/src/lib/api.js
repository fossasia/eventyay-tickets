/* global ENV_DEVELOPMENT */
import config from 'config'
import store from 'store'
import WebSocketClient from './WebSocketClient'

const api = Object.create(WebSocketClient.prototype)
api.connect = function ({token, clientId}) {
	if (api._socket) {
		api.close()
	}
	const client = new WebSocketClient(`${config.api.socket}`, {token, clientId})
	Object.assign(api, client)
	console.log(api)
	api.on('closed', () => {
		console.warn('socket closed')
	})

	api.on('error', (error) => {
		console.error('socket', error)
	})

	api.on('warning', (warning) => {
		console.warn('socket', warning)
	})

	api.on('message', (message) => {
		let [name, ...data] = message
		if (data.length === 1) data = data[0]
		const module = name.split('.')[0]
		if (store._actions[`${module}/api::${name}`]) {
			store.dispatch(`${module}/api::${name}`, data)
		} else if (store._actions[`api::${name}`]) {
			store.dispatch(`api::${name}`, data)
		}
	})

	api.on('log', ({direction, data}) => {
		const payload = JSON.parse(data)
		const action = payload.shift()
		let correlationId
		if (Number.isInteger(payload[0])) {
			correlationId = payload.shift()
		}
		if (['ping', 'pong'].includes(action)) return // mute pingpong
		if (ENV_DEVELOPMENT) {
			console.log(
				`%c${direction === 'send' ? '<<=' : '=>>'} %c${'socket'.padEnd(11)} %c${action.padEnd(32)} %c${String(correlationId || '').padEnd(6)}`,
				direction === 'send' ? 'color: blue' : 'color: green',
				'color: grey',
				'color: purple',
				'color: darkslategray',
				...payload
			)
		}
	})
}

export default api

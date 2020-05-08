const WebSocket = require('ws')
const { v4: uuid } = require('uuid')
module.exports = function (clientNumber, MESSAGES_PER_CLIENT_PER_SECOND, pingCb, timingCb) {
	const ws = new WebSocket('ws://localhost:8000/ws/world/sample/')
	let worldConfig
	let chatModule
	let correlationId = 1
	const clientId = uuid()
	ws.on('open', function () {
		ws.send(JSON.stringify(['authenticate', {client_id: clientId}]))
	})
	let lastPing

	ws.on('error', function (error) {
		console.log(error.toString())
	})

	incoming = function (data) {
		// console.log(data)
		if (data.startsWith(`["authenticated"`)) {
			const payload = JSON.parse(data)
			world = payload[1]['world.config']
			for (const room of world.rooms) {
				chatModule = room.modules.find(m => m.type === 'chat.native')
				if (chatModule) break
			}
			ws.send(JSON.stringify(['user.update', correlationId++, {
				profile: {display_name: `client ${clientNumber}`},
			}]))
			ws.send(JSON.stringify(['chat.subscribe', correlationId++, {
				channel: chatModule.channel_id,
			}]))
			spam()
			ping()
		} else if (data.startsWith(`["pong"`)) {
			pingCb(Date.now() - lastPing)
			lastPing = null
		} else if (data.startsWith(`["chat.event"`)) {
			const payload = JSON.parse(data)
			if (payload[1].content.client === clientId) {
				timingCb(Date.now() - payload[1].content.timestamp)
			}
		}
	}

	ws.on('message', incoming)

	const ping = function () {
		if (lastPing) {
			pingCb(Date.now() - lastPing)
			console.log('ping timeout')
			return
		}
		lastPing = Date.now()
		ws.send(JSON.stringify(['ping', lastPing]))
		setTimeout(ping, 5000)
	}

	const spam = function () {
		ws.send(JSON.stringify(['chat.send', correlationId++, {
			channel: chatModule.channel_id,
			event_type: 'channel.message',
			content: {type: 'text', client: clientId, timestamp: Date.now()}
		}]))
		console.log(`client ${clientNumber} sent message`)
		setTimeout(spam, 500 * MESSAGES_PER_CLIENT_PER_SECOND + Math.random() * 1000 / MESSAGES_PER_CLIENT_PER_SECOND)
	}
}

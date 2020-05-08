const WebSocket = require('ws')
const { v4: uuid } = require('uuid')
module.exports = function (clientNumber, MESSAGES_PER_CLIENT_PER_SECOND, pingCb) {
	const ws = new WebSocket('ws://localhost:8000/ws/world/sample/')
	let worldConfig
	let chatModule
	let correlationId = 1
	ws.on('open', function () {
		ws.send(JSON.stringify(['authenticate', {client_id: uuid()}]))
	})
	let lastPing

	ws.on('error', function (error) {
		console.error(error.toString())
	})

	incoming = function (data) {
		// console.log(data)
		const payload = JSON.parse(data)
		if (payload[0] === 'authenticated') {
			world = payload[1]['world.config']
			for (const room of world.rooms) {
				chatModule = room.modules.find(m => m.type === 'chat.native')
				if (chatModule) break
			}
			// we won't need anymore messages
			// ws.off('message', incoming)
			ws.send(JSON.stringify(['user.update', correlationId++, {
				profile: {display_name: `client ${clientNumber}`},
			}]))
			ws.send(JSON.stringify(['chat.subscribe', correlationId++, {
				channel: chatModule.channel_id,
			}]))
			spam()
			ping()
		} else if (payload[0] === 'pong') {
			pingCb(Date.now() - lastPing)
			lastPing = null
		}
	}

	ws.on('message', incoming)

	const ping = function () {
		if (lastPing) {
			pingCb(Date.now() - lastPing)
			console.error('ping timeout')
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
			content: {type: 'text', body: 'text'}
		}]))
		console.log(`client ${clientNumber} sent message`)
		setTimeout(spam, Math.random() * 1000 / MESSAGES_PER_CLIENT_PER_SECOND)
	}
}

const WebSocket = require('ws')
const { v4: uuid } = require('uuid')
module.exports = function (clientNumber, MESSAGES_PER_CLIENT_PER_SECOND) {
	const ws = new WebSocket('ws://localhost:8000/ws/world/sample/')
	let worldConfig
	let chatModule
	let correlationId = 1
	ws.on('open', function () {
		ws.send(JSON.stringify(['authenticate', {client_id: uuid()}]))
	})

	ws.on('error', function (error) {
		console.error(error)
	})

	incoming = function (data) {
		const payload = JSON.parse(data)
		if (payload[0] === 'authenticated') {
			world = payload[1]['world.config']
			for (const room of world.rooms) {
				chatModule = room.modules.find(m => m.type === 'chat.native')
				if (chatModule) break
			}
			// we won't need anymore messages
			ws.off('message', incoming)
			ws.send(JSON.stringify(['user.update', correlationId++, {
				profile: {display_name: `client ${clientNumber}`},
			}]))
			ws.send(JSON.stringify(['chat.join', correlationId++, {
				channel: chatModule.channel_id,
			}]))
			spam()
		}
	}

	ws.on('message', incoming)

	const spam = function () {
		ws.send(JSON.stringify(['chat.send', correlationId++, {
			channel: chatModule.channel_id,
			event_type: 'channel.message',
			content: {type: 'text', body: 'text'}
		}]))
		console.log(`client ${clientNumber} sent message`)
		setTimeout(spam, 1000/MESSAGES_PER_CLIENT_PER_SECOND)
	}
}

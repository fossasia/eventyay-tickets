import api from 'lib/api'

export default {
	namespaced: true,
	state: {
		timeline: []
	},
	getters: {},
	mutations: {},
	actions: {
		join ({state}, room) {
			api.client.call('chat.join', {room: room.id})
			// TODO wait for join confirmation
		},
		sendMessage ({state}, {room, text}) {
			api.client.call('chat.send', {
				room: room.id,
				event_type: 'message',
				content: {
					type: 'text',
					body: text
				}
			})
		},
		// INCOMING
		'api::chat.event' ({state}, payload) {
			state.timeline.push(payload)
		}
	}
}

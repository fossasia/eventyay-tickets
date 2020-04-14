import api from 'lib/api'

export default {
	namespaced: true,
	state: {
		timeline: []
	},
	getters: {},
	mutations: {},
	actions: {
		subscribe ({state}, channel) {
			api.call('chat.subscribe', {channel})
			// TODO wait for join confirmation
		},
		unsubscribe ({state}, channel) {
			api.call('chat.unsubscribe', {channel})
			// TODO wait for join confirmation
		},
		join ({state}, channel) {
			api.call('chat.join', {channel})
			// TODO wait for join confirmation
		},
		sendMessage ({state}, {channel, text}) {
			api.call('chat.send', {
				channel: channel,
				event_type: 'channel.message',
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

import api from 'lib/api'

export default {
	namespaced: true,
	state: {
		channel: null,
		hasJoined: false,
		members: [],
		timeline: []
	},
	getters: {},
	mutations: {},
	actions: {
		async subscribe ({state, dispatch}, channel) {
			if (state.channel) {
				dispatch('unsubscribe')
			}
			const {members} = await api.call('chat.subscribe', {channel})
			state.channel = channel
			state.hasJoined = Boolean(localStorage[`chat-channel-joined:${channel}`])
			state.members = members
			state.timeline = []
			if (state.hasJoined) {
				dispatch('join')
			}
		},
		async unsubscribe ({state}) {
			if (!state.channel) return
			state.channel = null
			await api.call('chat.unsubscribe', {channel: state.channel})
		},
		async join ({state}) {
			await api.call('chat.join', {channel: state.channel})
			state.hasJoined = true
			localStorage[`chat-channel-joined:${state.channel}`] = true
		},
		sendMessage ({state}, {text}) {
			api.call('chat.send', {
				channel: state.channel,
				event_type: 'channel.message',
				content: {
					type: 'text',
					body: text
				}
			})
		},
		// INCOMING
		'api::chat.event' ({state}, event) {
			switch (event.event_type) {
				case 'channel.message': state.timeline.push(event); break
				case 'channel.member': break
			}
		}
	}
}

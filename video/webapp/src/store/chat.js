import Vue from 'vue'
import api from 'lib/api'

export default {
	namespaced: true,
	state: {
		channel: null,
		hasJoined: false,
		members: [],
		membersLookup: {},
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
			const channel = state.channel
			state.channel = null
			if (api.socketState !== 'open') return
			await api.call('chat.unsubscribe', {channel})
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
			const handleMembership = (event) => {
				switch (event.content.membership) {
					case 'join': {
						state.members.push(event.content.user)
						Vue.set(state.membersLookup, event.content.user.id, event.content.user)
						break
					}
					case 'leave':
					case 'ban': {
						const index = state.members.findIndex(user => user.id === event.content.user.id)
						if (index >= 0) {
							state.members.splice(index, 1)
						}
						Vue.remove(state.membersLookup, event.content.user.id)
						break
					}
				}
			}
			switch (event.event_type) {
				case 'channel.message': state.timeline.push(event); break
				case 'channel.member': handleMembership(event); break
			}
		}
	}
}

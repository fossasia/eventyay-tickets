import Vue from 'vue'
import api from 'lib/api'

export default {
	namespaced: true,
	state: {
		channel: null,
		hasJoined: false,
		members: [],
		usersLookup: {},
		timeline: [],
		beforeCursor: null,
		fetchingMessages: false
	},
	getters: {},
	mutations: {},
	actions: {
		disconnected ({state}) {
			state.channel = null
		},
		async subscribe ({state, dispatch, rootState}, channel) {
			if (!rootState.connected) return
			if (state.channel) {
				dispatch('unsubscribe')
			}
			const { next_event_id: beforeCursor, members } = await api.call('chat.subscribe', {channel})
			state.channel = channel
			state.hasJoined = Boolean(localStorage[`chat-channel-joined:${channel}`])
			state.members = members
			state.usersLookup = members.reduce((acc, member) => { acc[member.id] = member; return acc }, {})
			state.timeline = []
			state.beforeCursor = beforeCursor
			dispatch('fetchMessages')
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
		async fetchMessages ({state, dispatch}) {
			if (!state.beforeCursor || state.fetchingMessages) return
			state.fetchingMessages = true
			const {results} = await api.call('chat.fetch', {channel: state.channel, count: 25, before_id: state.beforeCursor})
			state.timeline.unshift(...results)
			// assume past events don't just appear and stop forever when results are smaller than count
			state.beforeCursor = results.length < 25 ? null : results[0].event_id
			state.fetchingMessages = false
			// hit the user profile cache for each message
			for (const event of results) {
				if (!state.usersLookup[event.sender]) {
					await dispatch('fetchUser', event.sender)
				}
				if (event.content.user && !state.usersLookup[event.content.user.id]) {
					await dispatch('fetchUser', event.content.user.id)
				}
			}
		},
		async fetchUser ({state}, id) {
			const user = await api.call('user.fetch', {id})
			Vue.set(state.usersLookup, user.id, user)
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
		updateUser ({state}, {id, update}) {
			if (!state.usersLookup[id]) return
			for (const [key, value] of Object.entries(update)) {
				Vue.set(state.usersLookup[id], key, value)
			}
		},
		// INCOMING
		'api::chat.event' ({state}, event) {
			if (event.channel !== state.channel) return
			const handleMembership = (event) => {
				switch (event.content.membership) {
					case 'join': {
						state.members.push(event.content.user)
						Vue.set(state.usersLookup, event.content.user.id, event.content.user)
						break
					}
					case 'leave':
					case 'ban': {
						const index = state.members.findIndex(user => user.id === event.content.user.id)
						if (index >= 0) {
							state.members.splice(index, 1)
						}
						// Vue.delete(state.usersLookup, event.content.user.id)
						break
					}
				}
			}
			state.timeline.push(event)
			switch (event.event_type) {
				case 'channel.message': break
				case 'channel.member': handleMembership(event); break
			}
		}
	}
}

// TODO
// - volatile channels are automatically left, so we should remove them from `joinedChannels`. Leaving them in does not make any difference right now though.

import Vue from 'vue'
import api from 'lib/api'

export default {
	namespaced: true,
	state: {
		joinedChannels: null,
		channel: null,
		members: [],
		usersLookup: {},
		timeline: [],
		beforeCursor: null,
		fetchingMessages: false
	},
	getters: {
		hasJoinedChannel (state) {
			return state.joinedChannels.includes(state.channel)
		}
	},
	mutations: {
		setJoinedChannels (state, channels) {
			state.joinedChannels = channels
		}
	},
	actions: {
		disconnected ({state}) {
			state.channel = null
		},
		async subscribe ({state, dispatch, rootState}, {channel, config}) {
			if (!rootState.connected) return
			if (state.channel) {
				dispatch('unsubscribe')
			}
			const { next_event_id: beforeCursor, members } = await api.call('chat.subscribe', {channel})
			state.channel = channel
			state.members = members
			state.usersLookup = members.reduce((acc, member) => { acc[member.id] = member; return acc }, {})
			state.timeline = []
			state.beforeCursor = beforeCursor
			dispatch('fetchMessages')
			if (config?.volatile) { // autojoin volatile channels
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
			state.joinedChannels.push(state.channel)
		},
		async fetchMessages ({state, dispatch}) {
			if (!state.beforeCursor || state.fetchingMessages) return
			state.fetchingMessages = true
			const {results} = await api.call('chat.fetch', {channel: state.channel, count: 25, before_id: state.beforeCursor})
			// rely on the backend to have resolved all edits and deletes, filter deleted messages in view
			state.timeline.unshift(...results)
			// assume past events don't just appear and stop forever when results are smaller than count
			state.beforeCursor = results.length < 25 ? null : results[0].event_id
			state.fetchingMessages = false
			// hit the user profile cache for each message
			const missingProfiles = new Set()
			for (const event of results) {
				if (!state.usersLookup[event.sender]) {
					missingProfiles.add(event.sender)
				}
				if (event.content.user && !state.usersLookup[event.content.user.id]) {
					missingProfiles.add(event.content.user.id)
				}
			}
			await dispatch('fetchUsers', Array.from(missingProfiles))
		},
		async fetchUsers ({state}, ids) {
			const users = await api.call('user.fetch', {ids})
			for (const user of Object.values(users)) {
				Vue.set(state.usersLookup, user.id, user)
			}
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
		deleteMessage ({state}, message) {
			api.call('chat.send', {
				channel: state.channel,
				event_type: 'channel.message',
				replaces: message.event_id,
				content: {
					type: 'deleted'
				}
			})
		},
		editMessage ({state}, {message, newBody}) {
			api.call('chat.send', {
				channel: state.channel,
				event_type: 'channel.message',
				replaces: message.event_id,
				content: {
					type: 'text',
					body: newBody
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
			if (event.replaces) {
				if (event.content?.type === 'deleted') {
					const removeIndex = state.timeline.findIndex(msg => msg.event_id === event.replaces)
					if (removeIndex) {
						state.timeline.splice(removeIndex, 1)
					}
				} else {
					// TODO resolve edit chain?
					const replaceIndex = state.timeline.findIndex(msg => msg.event_id === event.replaces)
					if (replaceIndex) {
						state.timeline.splice(replaceIndex, 1, event)
					}
				}
			} else {
				state.timeline.push(event)
			}
			switch (event.event_type) {
				case 'channel.message': break
				case 'channel.member': handleMembership(event); break
			}
		},
		'api::chat.channels' ({state}, {channels}) {
			state.joinedChannels = channels
		}
	}
}

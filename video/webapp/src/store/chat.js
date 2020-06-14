// TODO
// - volatile channels are automatically left, so we should remove them from `joinedChannels`. Leaving them in does not make any difference right now though. OUTDATED?
// - use map for joinedChannels

import Vue from 'vue'
import api from 'lib/api'

export default {
	namespaced: true,
	state: {
		joinedChannels: null,
		readPointers: null,
		channel: null,
		members: [],
		usersLookup: {},
		timeline: [],
		beforeCursor: null,
		fetchingMessages: false
	},
	getters: {
		activeJoinedChannel (state) {
			return state.joinedChannels?.find(channel => channel.id === state.channel)
		},
		hasUnreadMessages (state) {
			return function (channel) {
				const joinedChannel = state.joinedChannels?.find(c => c.id === channel)
				return joinedChannel && (!state.readPointers[channel] || joinedChannel.notification_pointer > state.readPointers[channel])
			}
		}
	},
	mutations: {
		setJoinedChannels (state, channels) {
			state.joinedChannels = channels
		},
		setReadPointers (state, readPointers) {
			state.readPointers = readPointers
		}
	},
	actions: {
		disconnected ({state}) {
			state.channel = null
		},
		async subscribe ({state, dispatch, getters, rootState}, {channel, config}) {
			if (!rootState.connected) return
			if (state.channel) {
				dispatch('unsubscribe')
			}
			const { next_event_id: beforeCursor, members, notification_pointer: notificationPointer } = await api.call('chat.subscribe', {channel})
			state.channel = channel
			state.members = members
			state.usersLookup = members.reduce((acc, member) => { acc[member.id] = member; return acc }, {})
			state.timeline = []
			state.beforeCursor = beforeCursor
			if (getters.activeJoinedChannel) {
				getters.activeJoinedChannel.notification_pointer = notificationPointer
			}
			if (config?.volatile) { // autojoin volatile channels
				dispatch('join')
			}
			await dispatch('fetchMessages')
			dispatch('markChannelRead')
		},
		async unsubscribe ({state}) {
			if (!state.channel) return
			const channel = state.channel
			state.channel = null
			if (api.socketState !== 'open') return
			await api.call('chat.unsubscribe', {channel})
		},
		async join ({state}) {
			const response = await api.call('chat.join', {channel: state.channel})
			state.joinedChannels.push({id: state.channel, notification_pointer: response.notification_pointer})
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
		async markChannelRead ({state}) {
			const pointer = state.timeline[state.timeline.length - 1].event_id
			await api.call('chat.mark_read', {
				channel: state.channel,
				id: pointer
			})
			Vue.set(state.readPointers, state.channel, pointer)
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
		async moderateUser ({state}, {user, action}) {
			const postStates = {
				ban: 'banned',
				silence: 'silence',
				reactivate: null
			}
			await api.call(`user.${action}`, {id: user.id})
			if (state.usersLookup[user.id]) {
				state.usersLookup[user.id].moderation_state = postStates[action]
			}
			// user.moderation_state = postStates[action]
		},
		// INCOMING
		'api::chat.event' ({state, dispatch}, event) {
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
				// handle replaces like the server would
				const original = state.timeline.find(msg => msg.event_id === event.replaces)
				if (original) {
					original.content = event.content
				}
			}
			// always push event, even when it is a modifying event => consistent with what server returns on fetch
			state.timeline.push(event)
			switch (event.event_type) {
				case 'channel.message': break
				case 'channel.member': handleMembership(event); break
			}
			dispatch('markChannelRead')
		},
		'api::chat.channels' ({state}, {channels}) {
			state.joinedChannels = channels
		},
		'api::chat.read_pointers' ({state}, readPointers) {
			for (const [channel, pointer] of Object.entries(readPointers)) {
				Vue.set(state.readPointers, channel, pointer)
			}
		},
		'api::chat.notification_pointers' ({state}, notificationPointers) {
			for (const [channelId, pointer] of Object.entries(notificationPointers)) {
				const channel = state.joinedChannels.find(c => c.id === channelId)
				if (!channel) continue
				channel.notification_pointer = pointer
			}
		}
	}
}

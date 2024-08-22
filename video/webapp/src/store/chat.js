// TODO
// - volatile channels are automatically left, so we should remove them from `joinedChannels`. Leaving them in does not make any difference right now though. OUTDATED?
// - use map for joinedChannels

import Vue from 'vue'
import api from 'lib/api'
import router from 'router'
import i18n from 'i18n'
import { contentToPlainText } from 'components/ChatContent'

export default {
	namespaced: true,
	state: {
		call: null,
		joinedChannels: null,
		readPointers: null,
		notificationCounts: null,
		channel: null,
		config: null,
		members: [],
		usersLookup: {},
		timeline: [],
		beforeCursor: null,
		fetchingMessages: false,
		warnings: []
	},
	getters: {
		activeJoinedChannel(state) {
			return state.joinedChannels?.find(channel => channel.id === state.channel)
		},
		// TODO maybe merge this with joinedChannels?
		automaticallyJoinedChannels(state, getters, rootState) {
			return rootState.rooms.map(room => room.modules.find(m => m.type === 'chat.native')).filter(m => m?.config?.volatile).map(m => m.channel_id)
		},
		hasUnreadMessages(state) {
			return function(channel) {
				const joinedChannel = state.joinedChannels?.find(c => c.id === channel)
				return joinedChannel && (!state.readPointers[channel] || joinedChannel.unread_pointer > state.readPointers[channel])
			}
		},
		notificationCount(state) {
			return function(channel) {
				return state.notificationCounts[channel] || 0
			}
		},
		// TODO this is BAD
		isDirectMessageChannel(state, getters, rootState) {
			return function(channel) {
				return channel.members && channel.members.some(member => member.id !== rootState.user.id)
			}
		},
		channelName(state, getters, rootState) {
			return function(channel) {
				if (this.isDirectMessageChannel(channel)) {
					return this.directMessageChannelName(channel)
				} else {
					return rootState.rooms.find(room => room.modules.some(m => m.channel_id === channel.id)).name
				}
			}
		},
		directMessageChannelName(state, getters, rootState) {
			return function(channel) {
				return channel.members.filter(user => user.id !== rootState.user.id).map(user => user.profile.display_name).join(', ')
			}
		}
	},
	mutations: {
		setJoinedChannels(state, channels) {
			state.joinedChannels = channels
		},
		setReadPointers(state, readPointers) {
			state.readPointers = readPointers
		},
		setNotificationCounts(state, notificationCounts) {
			state.notificationCounts = notificationCounts
		},
	},
	actions: {
		disconnected({state}) {
			state.channel = null
		},
		async subscribe({state, dispatch, getters, rootState}, {channel, config}) {
			if (!rootState.connected) return
			if (state.channel) {
				dispatch('unsubscribe')
			}
			const { next_event_id: beforeCursor, members, unread_pointer: notificationPointer } = await api.call('chat.subscribe', {channel})
			state.channel = channel
			state.members = members
			state.usersLookup = members.reduce((acc, member) => { acc[member.id] = member; return acc }, {})
			state.timeline = []
			state.warnings = []
			state.beforeCursor = beforeCursor
			state.config = config
			if (getters.activeJoinedChannel) {
				getters.activeJoinedChannel.unread_pointer = notificationPointer
			}
			if (config?.volatile) { // autojoin volatile channels
				dispatch('join')
			}
			await dispatch('fetchMessages')
			dispatch('markChannelRead')
		},
		async unsubscribe({state}) {
			if (!state.channel) return
			const channel = state.channel
			state.channel = null
			if (api.socketState !== 'open') return
			await api.call('chat.unsubscribe', {channel})
		},
		async join({state}, channel) {
			channel = channel?.modules[0]?.channel_id
			const response = await api.call('chat.join', {channel: channel || state.channel})
			state.joinedChannels.push({id: channel || state.channel, unread_pointer: response.unread_pointer})
		},
		async fetchMessages({state, dispatch}) {
			if (!state.beforeCursor || state.fetchingMessages) return
			state.fetchingMessages = true
			try {
				const channel = state.channel
				const {results, users} = await api.call('chat.fetch', {channel, count: 25, before_id: state.beforeCursor})
				// have we left the channel already?
				if (channel !== state.channel) return
				// rely on the backend to have resolved all edits and deletes, filter deleted messages in view
				state.timeline.unshift(...results)
				// cache profiles the server sent us
				for (const user of Object.values(users)) {
					Vue.set(state.usersLookup, user.id, user)
				}
				// assume past events don't just appear and stop forever when results are smaller than count
				state.beforeCursor = results.length < 25 ? null : results[0].event_id
				// hit the user profile cache for each message
				// TODO search for mentions
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
			} catch (e) {
				console.error(e)
				// TODO show error
			}
			state.fetchingMessages = false
		},
		async markChannelRead({state}) {
			if (state.timeline.length === 0) return
			if (state.config?.volatile && !state.notificationCounts[state.channel]) return
			const pointer = state.timeline[state.timeline.length - 1].event_id
			await api.call('chat.mark_read', {
				channel: state.channel,
				id: pointer
			})
			Vue.set(state.readPointers, state.channel, pointer)
		},
		async fetchUsers({state}, ids) {
			if (!ids?.length) return
			const users = await api.call('user.fetch', {ids})
			for (const user of Object.values(users)) {
				Vue.set(state.usersLookup, user.id, user)
			}
		},
		sendMessage({state}, {content}) {
			api.call('chat.send', {
				channel: state.channel,
				event_type: 'channel.message',
				content
			})
		},
		deleteMessage({state}, message) {
			api.call('chat.send', {
				channel: state.channel,
				event_type: 'channel.message',
				replaces: message.event_id,
				content: {
					type: 'deleted'
				}
			})
		},
		editMessage({state}, {message, content}) {
			api.call('chat.send', {
				channel: state.channel,
				event_type: 'channel.message',
				replaces: message.event_id,
				content
			})
		},
		updateUser({state}, {id, update}) {
			if (!state.usersLookup[id]) return
			for (const [key, value] of Object.entries(update)) {
				Vue.set(state.usersLookup[id], key, value)
			}
		},
		async moderateUser({state}, {user, action}) {
			const postStates = {
				ban: 'banned',
				silence: 'silence',
				reactivate: null
			}
			await api.call(`user.${action}`, {id: user.id})
			if (state.usersLookup[user.id] && typeof postStates[action] !== 'undefined') {
				state.usersLookup[user.id].moderation_state = postStates[action]
			}
			// user.moderation_state = postStates[action]
		},
		async blockUser({state}, {user}) {
			await api.call('user.block', {id: user.id})
		},
		async openDirectMessage({state}, {users, hide}) {
			let channel = state.joinedChannels.find(channel => channel.members?.length === users.length + 1 && users.every(user => channel.members.some(member => member.id === user.id)))
			if (hide !== false) {
				hide = true
			}
			if (!channel) {
				channel = await api.call('chat.direct.create', {users: users.map(user => user.id), hide: hide})
				state.joinedChannels.push(channel)
			}
			if (router.currentRoute.name !== 'channel' || router.currentRoute.params.channelId !== channel.id) {
				await router.push({name: 'channel', params: {channelId: channel.id}})
			}
			return channel
		},
		async leaveChannel({state}, {channelId}) {
			await api.call('chat.leave', {channel: channelId})
			if (router.currentRoute.name === 'channel' && router.currentRoute.params.channelId === channelId) {
				await router.push({name: 'home'})
			}
			const index = state.joinedChannels.findIndex(c => c.id === channelId)
			if (index > -1) state.joinedChannels.splice(index, 1)
		},
		async startCall({state, dispatch}, {channel}) {
			const {event} = await api.call('chat.send', {
				channel: channel.id,
				event_type: 'channel.message',
				content: {
					type: 'call'
				}
			})
			dispatch('joinCall', event.content.body)
		},
		async joinCall({state}, body) {
			if (body.type === 'janus') {
				state.call = {
					type: 'janus',
					id: state.channel,
					parameters: await api.call('januscall.channel_url', {channel: state.channel}),
					channel: state.channel
				}
			} else {
				// We need to create the window right away, otherwise Safari will not believe this to be caused by the user
				const win = window.open()
				win.document.write('Please wait a second ...')
				try {
					const {url} = await api.call('bbb.call_url', {call: body.id})
					win.location = url
				} catch (e) {
					console.error(e)
					win.close()
				}
			}
		},
		async leaveCall({state}) {
			state.call = null
		},
		addReaction({state}, {message, reaction}) {
			// TODO skip if already reacted
			return api.call('chat.react', {
				channel: state.channel,
				event: message.event_id,
				reaction
			})
		},
		removeReaction({state}, {message, reaction}) {
			return api.call('chat.react', {
				channel: state.channel,
				event: message.event_id,
				reaction,
				delete: true
			})
		},
		dismissWarnings({state}) {
			state.warnings = []
		},
		// INCOMING
		async 'api::chat.event'({state, dispatch}, event) {
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

			// hit the user profile cache for each message
			if (event.users) {
				for (const user of Object.values(event.users)) {
					Vue.set(state.usersLookup, user.id, user)
				}
			}
			if (!state.usersLookup[event.sender]) {
				await dispatch('fetchUsers', [event.sender])
			}
		},
		'api::chat.channels'({state}, {channels}) {
			state.joinedChannels = channels
		},
		'api::chat.read_pointers'({state}, readPointers) {
			for (const [channel, pointer] of Object.entries(readPointers)) {
				Vue.set(state.readPointers, channel, pointer)
				// TODO passively close desktop notifications
			}
		},
		'api::chat.unread_pointers'({state, rootState, getters, dispatch}, unreadPointers) {
			for (const [channelId, pointer] of Object.entries(unreadPointers)) {
				const channel = state.joinedChannels.find(c => c.id === channelId)
				if (!channel) continue
				channel.unread_pointer = pointer
			}
		},
		'api::chat.notification_counts'({state, rootState, getters, dispatch}, notificationCounts) {
			state.notificationCounts = notificationCounts
		},
		async 'api::chat.notification'({state, rootState, getters, dispatch}, data) {
			const channelId = data.event.channel
			const channel = state.joinedChannels.find(c => c.id === channelId) || getters.automaticallyJoinedChannels.includes(channelId) ? {id: channelId} : null
			if (!channel) return
			// Increment notification count
			Vue.set(state.notificationCounts, channel.id, (state.notificationCounts[channel.id] || 0) + 1)
			// TODO show desktop notification when window in focus but route is somewhere else?
			let body = i18n.t('DirectMessage:notification-unread:text')
			if (data.event.content.type === 'text') {
				// TODO parse @uuid mentions
				body = data.event.content.body
			}
			// TODO handle image-only message
			dispatch('notifications/createDesktopNotification', {
				title: getters.channelName(channel),
				body: await contentToPlainText(body),
				tag: getters.channelName(channel),
				user: data.sender,
				// TODO onClose?
				onClick: () => {
					if (getters.isDirectMessageChannel(channel))
						router.push({name: 'channel', params: {channelId: channel.id}})
					else
						router.push({name: 'room', params: {roomId: rootState.rooms.find(room => room.modules.some(m => m.channel_id === channel.id)).id}})
				}
			}, {root: true})
		},
		'api::chat.event.reaction'({state}, event) {
			if (event.channel !== state.channel) return
			const original = state.timeline.find(msg => msg.event_id === event.event_id)
			if (original) {
				original.reactions = event.reactions
			}
			if (event.users) {
				for (const user of Object.values(event.users)) {
					Vue.set(state.usersLookup, user.id, user)
				}
			}
		},
		'api::chat.mention_warning'({state}, data) {
			state.warnings.push(data)
		}
	}
}

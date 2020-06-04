import Vue from 'vue'
import Vuex from 'vuex'
import api from 'lib/api'
import router from 'router'
import chat from './chat'

Vue.use(Vuex)

export default new Vuex.Store({
	state: {
		token: null,
		clientId: null,
		connected: false,
		fatalConnectionError: null,
		fatalError: null,
		user: null,
		world: null,
		rooms: null,
		permissions: null,
		schedule: null,
		activeRoom: null,
		streamingRoom: null,
		reactions: null
	},
	getters: {
		hasPermission (state) {
			return (permission) => {
				return !!state.permissions?.includes(permission)
			}
		}
	},
	actions: {
		login ({state}, {token, clientId}) {
			state.token = token
			state.clientId = clientId
		},
		connect ({state, dispatch, commit}) {
			api.connect({token: state.token, clientId: state.clientId})
			api.on('joined', (serverState) => {
				state.connected = true
				state.user = serverState['user.config']
				state.world = serverState['world.config'].world
				state.permissions = serverState['world.config'].permissions
				commit('chat/setJoinedChannels', serverState['chat.channels'])
				if (!state.rooms) {
					state.rooms = serverState['world.config'].rooms
				} else {
					const updatedRooms = []
					for (const newRoom of serverState['world.config'].rooms) {
						const oldRoom = state.rooms.find(r => r.id === newRoom.id)
						if (oldRoom) {
							Object.assign(oldRoom, newRoom) // good enough?
							updatedRooms.push(oldRoom)
						} else {
							state.rooms.push(newRoom)
						}
					}
					for (const oldRoom of state.rooms) {
						if (!updatedRooms.includes(oldRoom)) {
							const index = state.rooms.indexOf(oldRoom)
							if (index >= 0) {
								state.rooms.splice(index, 1)
							}
						}
					}
				}
				if (!state.user.profile.display_name) {
					router.push('/').catch(() => {}) // force new users to welcome page
					// TODO return after profile update?
				}
				dispatch('fetchSchedule')
			})
			api.on('closed', () => {
				state.connected = false
				state.activeRoom = null
				dispatch('chat/disconnected', {root: true})
			})
			api.on('error', error => {
				switch (error.code) {
					case 'world.unknown_world':
					case 'auth.invalid_token':
					case 'auth.denied':
					case 'auth.missing_id_or_token':
					case 'connection.replaced':
						state.fatalConnectionError = error
						api.close()
						break
					case 'server.fatal':
						state.fatalError = error
						api.close()
						break
				}
				// TODO handle generic fatal error?
			})
		},
		async updateUser ({state, dispatch}, update) {
			await api.call('user.update', update)
			for (const [key, value] of Object.entries(update)) {
				Vue.set(state.user, key, value)
			}
			dispatch('chat/updateUser', {id: state.user.id, update})
		},
		async fetchSchedule ({state}) {
			if (!state.world.pretalx?.base_url) return
			const schedule = await (await fetch(state.world.pretalx.base_url + 'schedule/widget/v1.json')).json()
			state.schedule = schedule
		},
		streamRoom ({state}, {room}) {
			state.streamingRoom = room
		},
		async createRoom ({state}, room) {
			return await api.call('room.create', room)
		},
		async enterRoom ({state, dispatch}, room) {
			if (!state.connected || !room) return
			if (state.activeRoom) {
				await dispatch('leaveRoom', {room: state.activeRoom})
			}
			state.activeRoom = room
			api.call('room.enter', {room: room.id})
		},
		async leaveRoom ({state}, room) {
			if (!state.activeRoom || state.activeRoom.id !== room.id) return
			state.activeRoom = null
			state.reactions = null
			if (api.socketState !== 'open') return
			api.call('room.leave', {room: room.id})
		},
		async addReaction ({state}, reaction) {
			if (!state.activeRoom) return
			await api.call('room.react', {room: state.activeRoom.id, reaction})
		},
		'api::room.create' ({state}, room) {
			state.rooms.push(room)
			// TODO ordering?
		},
		'api::room.reaction' ({state}, {room, reactions}) {
			if (state.activeRoom.id !== room) return
			state.reactions = reactions
		}
	},
	modules: {
		chat
	}
})

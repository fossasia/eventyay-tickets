import Vue from 'vue'
import Vuex from 'vuex'
import api from 'lib/api'
import router from 'router'
import chat from './chat'
import exhibition from './exhibition'

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
		reactions: null,
	},
	getters: {
		hasPermission (state) {
			return (permission) => {
				return !!state.permissions?.includes(permission)
			}
		}
	},
	mutations: {
		updateRooms (state, rooms) {
			// preserve object references for media source
			if (state.rooms) {
				for (const [index, newRoom] of rooms.entries()) {
					const oldRoom = state.rooms.find(r => r.id === newRoom.id)
					if (oldRoom) {
						Object.assign(oldRoom, newRoom) // good enough?
						rooms.splice(index, 1, oldRoom)
					}
				}
			}
			state.rooms = rooms
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
				commit('chat/setReadPointers', serverState['chat.read_pointers'])
				commit('exhibition/setData', serverState.exhibition)
				commit('updateRooms', serverState['world.config'].rooms)
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
		async createRoom ({state}, room) {
			return await api.call('room.create', room)
		},
		changeRoom ({state}, room) {
			state.activeRoom = room
			state.reactions = null
		},
		async addReaction ({state}, reaction) {
			if (!state.activeRoom) return
			await api.call('room.react', {room: state.activeRoom.id, reaction})
		},
		'api::room.create' ({state}, room) {
			state.rooms.push(room)
			// TODO ordering?
		},
		'api::room.delete' ({state}, {id}) {
			const index = state.rooms.findIndex(room => room.id === id)
			if (index >= 0) {
				state.rooms.splice(index, 1)
			}
		},
		'api::room.reaction' ({state}, {room, reactions}) {
			if (state.activeRoom.id !== room) return
			state.reactions = reactions
		},
		'api::world.updated' ({state, commit, dispatch}, {world, rooms, permissions}) {
			state.world = world
			state.permission = permissions
			commit('updateRooms', rooms)
			dispatch('fetchSchedule')
		},
		// TODO handle user.updated
	},
	modules: {
		chat,
		exhibition
	}
})

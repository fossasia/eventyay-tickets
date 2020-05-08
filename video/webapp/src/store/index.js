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
		user: null,
		world: null,
		rooms: null,
		schedule: null,
		streamingRoom: null
	},
	actions: {
		login ({state}, {token, clientId}) {
			state.token = token
			state.clientId = clientId
		},
		connect ({state, dispatch}) {
			api.connect({token: state.token, clientId: state.clientId})
			api.on('joined', (serverState) => {
				state.connected = true
				state.user = serverState['user.config']
				state.world = serverState['world.config'].world
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
		}
	},
	modules: {
		chat
	}
})

import Vue from 'vue'
import Vuex from 'vuex'
import moment from 'lib/timetravelMoment'
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
		now: moment(),
		activeRoom: null,
		reactions: null
	},
	getters: {
		hasPermission (state) {
			return (permission) => {
				return !!state.permissions?.includes(permission)
			}
		},
		flatSchedule (state) {
			if (!state.schedule) return
			const sessions = []
			for (const day of state.schedule.schedule) {
				for (const room of day.rooms) {
					const vRoom = state.rooms.find(r => r.import_id === state.world.pretalx.room_mapping[room.id])
					for (const talk of room.talks) {
						sessions.push({
							id: talk.code,
							title: talk.title,
							start: moment(talk.start),
							end: moment(talk.end),
							speakers: talk.speakers,
							room: vRoom
						})
					}
				}
			}
			sessions.sort((a, b) => a.start.diff(b.start))
			return {sessions}
		},
		sessionsScheduledNow (state, getters) {
			if (!getters.flatSchedule) return
			const sessions = []
			for (const session of getters.flatSchedule.sessions) {
				if (session.end.isBefore(state.now) || session.start.isAfter(state.now)) continue
				sessions.push(session)
			}
			return sessions
		}
	},
	mutations: {
		updateNow (state) {
			state.now = moment()
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
		async updateRoomSchedule ({state}, {room, schedule_data}) {
			return await api.call('room.schedule', {room: room.id, schedule_data})
		},
		'api::room.create' ({state}, room) {
			state.rooms.push(room)
			// TODO ordering?
		},
		'api::room.delete' ({state}, data) {
			state.rooms = state.rooms.filter((r) => (r.id !== data.id))
			if (state.activeRoom.id === data.id) {
				state.activeRoom = state.rooms[0]
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
		'api::room.schedule' ({state}, {room, schedule_data}) {
			room = state.rooms.find(r => r.id === room)
			if (!room) return
			Vue.set(room, 'schedule_data', schedule_data)
		}
		// TODO handle user.updated
	},
	modules: {
		chat
	}
})

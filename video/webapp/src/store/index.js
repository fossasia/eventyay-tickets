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
		user: null,
		world: null,
		rooms: null,
		schedule: null
	},
	actions: {
		login ({state}, {token, clientId}) {
			state.token = token
			state.clientId = clientId
		},
		connect ({state, dispatch}) {
			api.connect({token: state.token, clientId: state.clientId})
			api.on('joined', (serverState) => {
				state.user = serverState['user.config']
				state.world = serverState['world.config'].world
				state.rooms = serverState['world.config'].rooms
				if (!state.user.profile.display_name) {
					router.push('/').catch(() => {}) // force new users to welcome page
					// TODO return after profile update?
				}
				dispatch('fetchSchedule')
			})
			api.on('closed', () => {
				state.world = null
			})
		},
		async updateUser ({state}, update) {
			await api.call('user.update', update)
			for (const [key, value] of Object.entries(update)) {
				Vue.set(state.user, key, value)
			}
		},
		async fetchSchedule ({state}) {
			if (!state.world.pretalx?.schedule_url) return
			const schedule = await fetch(state.world.pretalx.schedule_url)
			console.log(schedule)
		}
	},
	modules: {
		chat
	}
})

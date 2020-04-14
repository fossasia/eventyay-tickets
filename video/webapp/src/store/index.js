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
		event: null,
		rooms: null
	},
	actions: {
		login ({state}, {token, clientId}) {
			state.token = token
			state.clientId = clientId
		},
		connect ({state}) {
			api.connect({token: state.token, clientId: state.clientId})
			api.on('joined', (serverState) => {
				state.user = serverState['user.config']
				state.event = serverState['event.config'].event
				state.rooms = serverState['event.config'].rooms
				if (!state.user.profile) {
					router.push('/').catch(() => {}) // force new users to welcome page
					// TODO return after profile update?
				}
			})
			api.on('closed', () => {
				state.event = null
			})
		},
		async updateUser ({state}, update) {
			// await api.call('user.update', update)
			for (const [key, value] of Object.entries(update)) {
				Vue.set(state.user, key, value)
			}
		}
	},
	modules: {
		chat
	}
})

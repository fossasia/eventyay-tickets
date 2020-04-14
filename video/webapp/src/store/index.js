import Vue from 'vue'
import Vuex from 'vuex'
import api from 'lib/api'
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
			})
			api.on('closed', () => {
				state.event = null
			})
		},
		async updateUser ({state}, update) {
			await api.call('user.update', update)
			Object.assign(state.user, update)
		}
	},
	modules: {
		chat
	}
})

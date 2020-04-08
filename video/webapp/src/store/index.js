import Vue from 'vue'
import Vuex from 'vuex'
import api from 'lib/api'
import chat from './chat'

Vue.use(Vuex)

export default new Vuex.Store({
	state: {
		event: null,
		rooms: null
	},
	actions: {
		connect ({commit, dispatch, state}) {
			api.connect()
			api.client.on('joined', (initialState) => {
				state.event = initialState.event
				state.rooms = initialState.rooms
			})
			api.client.on('closed', () => {
				state.event = null
			})
		}
	},
	modules: {
		chat
	}
})

import Vue from 'vue'
import Vuex from 'vuex'
import api from 'lib/api'

Vue.use(Vuex)

export default new Vuex.Store({
	state: {
		event: null,
		rooms: null
	},
	mutations: {
		SET_EVENT (state, event) {
			state.event = event
		},
		SET_ROOMS (state, rooms) {
			state.rooms = rooms
		}
	},
	actions: {
		connect ({commit, dispatch, state}) {
			api.connect()
			api.client.on('joined', (initialState) => {
				commit('SET_EVENT', initialState.event)
				commit('SET_ROOMS', initialState.rooms)
			})
		}
	}
})

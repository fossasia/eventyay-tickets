import api from 'lib/api'

export default {
	namespaced: true,
	state: {
		room: null,
		loading: false,
		callId: null,
		server: null,
		token: null,
		iceServers: [],
		roomId: null,
		error: null,
		requestTimer: null,
	},
	getters: {
	},
	mutations: {
		setLoading (state, value) {
			state.loading = value
		},
		setRoom (state, value) {
			state.room = value
		},
		setError (state, value) {
			state.error = value
		},
		setCallId (state, callId) {
			state.callId = callId
		},
		setJanusParameters (state, data) {
			state.server = data.server
			state.token = data.token
			state.iceServers = data.iceServers
			state.roomId = data.roomId
		},
	},
	actions: {
		startRequesting ({state, commit, dispatch}, {room}) {
			commit('setRoom', room)
			commit('setError', null)
			commit('setLoading', true)
			dispatch('request')
		},
		async request ({state, dispatch}) {
			const result = await api.call('roulette.start', {room: state.room.id})
			if (result.status === 'wait' && !state.callId) {
				state.requestTimer = window.setTimeout(() => dispatch('request'), 15000)
			} else if (result.status === 'match') {
				dispatch('startCall', {callId: result.call_id})
			}
		},
		async stopRequesting ({state, commit}) {
			commit('setError', null)
			commit('setLoading', false)
			if (state.requestTimer) {
				window.clearTimeout(state.requestTimer)
			}
			await api.call('roulette.stop', {room: state.room.id})
		},
		async startCall ({state, commit}, {callId}) {
			commit('setError', null)
			commit('setLoading', true)
			try {
				commit('setCallId', callId)
				const data = await api.call('januscall.roulette_url', {call_id: callId})
				commit('setJanusParameters', data)
				commit('setLoading', false)
			} catch (e) {
				commit('setError', e.message)
				commit('setLoading', false)
			}
		},
		async stopCall ({state, commit}) {
			const callId = state.callId
			commit('setJanusParameters', {callId: null, server: null, token: null, iceServers: null, roomId: null})
			commit('setCallId', null)
			if (callId) {
				await api.call('roulette.hangup', {call_id: callId})
			}
		},
		'api::roulette.hangup' ({state, commit}, payload) {
			commit('setCallId', null)
			commit('setJanusParameters', {callId: null, server: null, token: null, iceServers: null, roomId: null})
		},
		'api::roulette.match_found' ({state, dispatch}, payload) {
			if (state.requestTimer) {
				window.clearTimeout(state.requestTimer)
			}
			dispatch('startCall', {callId: payload.call_id})
		},
	}
}

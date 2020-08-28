import api from 'lib/api'
import router from 'router'

export default {
	namespaced: true,
	state: {
		staffedExhibitions: [],
		contactRequests: [],
	},
	getters: {
		openContactRequests (state) {
			return state.contactRequests.filter(cr => cr.state === 'open')
		}
	},
	mutations: {
		setData (state, data) {
			state.staffedExhibitions = data.exhibitors
			state.contactRequests = data.contact_requests
		}
	},
	actions: {
		async dismissContactRequest ({state}, contactRequest) {
			state.staffContactRequests = state.staffContactRequests.filter(function (r) { return r.id !== contactRequest.id })
		},
		async acceptContactRequest ({state, dispatch, rootState}, contactRequest) {
			// TODO error handling
			const channel = await dispatch('chat/openDirectMessage', {users: [contactRequest.user], hide: false}, {root: true})
			await api.call('exhibition.contact_accept', {contact_request: contactRequest.id, channel: channel.id})
			contactRequest.state = 'answered'
			contactRequest.answered_by = rootState.user
			contactRequest.timestamp = new Date().toISOString()
			// TODO: send greeting message
		},
		async 'api::exhibition.exhibition_data_update' ({commit, state}, {data}) {
			commit('setData', data)
		},
		// for staff
		'api::exhibition.contact_request' ({state}, data) {
			state.contactRequests.push(data.contact_request)
		},
		'api::exhibition.contact_request_close' ({state}, data) {
			const contactRequest = data.contact_request
			const existingContactRequest = state.contactRequests.find(cb => cb.id === contactRequest.id)
			if (!existingContactRequest) return
			existingContactRequest.state = contactRequest.state
			existingContactRequest.answered_by = contactRequest.answered_by
			existingContactRequest.timestamp = contactRequest.timestamp
		},
		// for client
		async 'api::exhibition.contact_accepted' ({dispatch}, data) {
			// DM is automatically opening
			await router.push({name: 'channel', params: {channelId: data.channel}})
		}

	}
}

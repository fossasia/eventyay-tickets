import api from 'lib/api'

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
			await dispatch('chat/openDirectMessage', {user: contactRequest.user}, {root: true})
			await api.call('exhibition.contact_accept', {contact_request: contactRequest.id})
			contactRequest.state = 'answered'
			contactRequest.answered_by = rootState.user
			contactRequest.timestamp = new Date().toISOString()
			// TODO: send greeting message
		},
		// for staff
		'api::exhibition.contact_request' ({state}, contactRequest) {
			state.contactRequests.push(contactRequest)
		},
		'api::exhibition.contact_request_close' ({state}, contactRequest) {
			const existingContactRequest = state.contactRequests.find(cb => cb.id === contactRequest.id)
			if (!existingContactRequest) return
			existingContactRequest.state = contactRequest.state
			existingContactRequest.answered_by = contactRequest.answered_by
			existingContactRequest.timestamp = contactRequest.timestamp
		},
		// for client
		async 'api::exhibition.contact_accepted' ({dispatch}, contactRequest) {
			await dispatch('chat/openDirectMessage', {user: contactRequest.answered_by}, {root: true})
		}
	}
}

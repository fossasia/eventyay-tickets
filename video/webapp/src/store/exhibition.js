import api from 'lib/api'

export default {
	namespaced: true,
	state: {
		staffContactRequests: [],
		userContactRequests: [],
	},
	getters: {
	},
	mutations: {
	},
	actions: {
		async contact ({state}, { exhibitorId, roomId }) {
			state.userContactRequests.push((await api.call('exhibition.contact', {exhibitor: exhibitorId, room: roomId})).contact_request)
		},
		async dismissContactRequest ({state}, contactRequest) {
			state.staffContactRequests = state.staffContactRequests.filter(function (r) { return r.id !== contactRequest.id })
		},
		async acceptContactRequest ({state, dispatch}, contactRequest) {
			await api.call('exhibition.contact_accept', {contact_request: contactRequest.id})
			await dispatch('chat/openDirectMessage', {user: contactRequest.user})
			// TODO: send greeting message
		},
		async closeContactRequest ({state}, contactRequest) {
			state.userContactRequests = state.userContactRequests.filter(function (r) { return r.id !== contactRequest.id })
		},
		'api::exhibition.contact_accepted' ({state}, contactRequest) {
			state.userContactRequests = state.userContactRequests.filter(function (r) { return r.id !== contactRequest.id })
		},
		'api::exhibition.contact_request' ({state}, contactRequest) {
			state.staffContactRequests.push(contactRequest)
		},
		'api::exhibition.contact_request_close' ({state}, contactRequest) {
			state.staffContactRequests = state.staffContactRequests.filter(function (r) { return r.id !== contactRequest.id })
		}
	}
}

import api from 'lib/api'
import router from 'router'
import i18n from 'i18n'

export default {
	namespaced: true,
	state: {
		staffedExhibitions: [],
		contactRequests: [],
	},
	getters: {
		openContactRequests(state) {
			return state.contactRequests.filter(cr => cr.state === 'open' && !cr.weDismissed)
		}
	},
	mutations: {
		setData(state, data) {
			state.staffedExhibitions = data.exhibitors
			state.contactRequests = data.contact_requests
		},
		addContactRequest(state, contactRequest) {
			state.contactRequests.push(contactRequest)
		},
		updateContactRequest(state, updatedRequest) {
			const index = state.contactRequests.findIndex(cr => cr.id === updatedRequest.id)
			if (index !== -1) {
				state.contactRequests.splice(index, 1, updatedRequest)
			}
		},
		dismissContactRequest(state, contactRequest) {
			const existing = state.contactRequests.find(cr => cr.id === contactRequest.id)
			if (existing) {
				existing.weDismissed = true
			}
		}
	},
	actions: {
		async acceptContactRequest({ state, commit, rootState }, contactRequest) {
			const channel = await this.dispatch('chat/openDirectMessage', {
				users: [contactRequest.user],
				hide: false
			}, { root: true })
			
			await api.call('exhibition.contact_accept', {
				contact_request: contactRequest.id,
				channel: channel.id
			})
			
			const updatedRequest = {
				...contactRequest,
				state: 'answered',
				answered_by: rootState.user,
				timestamp: new Date().toISOString()
			}
			
			commit('updateContactRequest', updatedRequest)
		},
		async 'api::exhibition.exhibition_data_update'({ commit }, { data }) {
			commit('setData', data)
		},
		async 'api::exhibition.contact_request'({ commit, dispatch }, data) {
			const contactRequest = data.contact_request
			commit('addContactRequest', contactRequest)
			
			await dispatch('notifications/createDesktopNotification', {
				title: contactRequest.user?.profile.display_name,
				body: i18n.t('ContactRequest:notification:text') + ' ' + contactRequest.exhibitor.name,
				user: contactRequest.user,
				// TODO onClose?
				onClick: () => dispatch('acceptContactRequest', contactRequest)
			}, { root: true })
		},
		'api::exhibition.contact_request_close'({ commit }, data) {
			const contactRequest = data.contact_request
			commit('updateContactRequest', {
				...contactRequest,
				state: contactRequest.state,
				answered_by: contactRequest.answered_by,
				timestamp: contactRequest.timestamp
			})
		},
		async 'api::exhibition.contact_accepted'({ dispatch }, data) {
			await router.push({ name: 'channel', params: { channelId: data.channel } })
		}
	}
}

// TODO sync dismissed announcements between tabs

import moment from 'moment'

export default {
	namespaced: true,
	state: {
		rawAnnouncements: [],
		dismissedAnnouncements: localStorage.dismissedAnnouncements ? JSON.parse(localStorage.dismissedAnnouncements) : [],
	},
	getters: {
		announcements(state, getters, rootState) {
			return state.rawAnnouncements.map(announcement => {
				const showUntil = announcement.show_until ? moment(announcement.show_until) : null
				return {
					...announcement,
					show_until: showUntil,
					expired: showUntil?.isBefore(rootState.now)
				}
			})
		},
		visibleAnnouncements(state, getters, rootState) {
			return getters.announcements.filter(announcement => 
				announcement.state === 'active' && 
				!announcement.expired && 
				!state.dismissedAnnouncements.includes(announcement.id)
			)
		}
	},
	mutations: {
		setAnnouncements(state, announcements) {
			state.rawAnnouncements = announcements.map(a => ({
				...a,
				show_until: a.show_until ? moment(a.show_until) : null
			}))
		},
		updateAnnouncement(state, updatedAnnouncement) {
			const index = state.rawAnnouncements.findIndex(a => a.id === updatedAnnouncement.id)
			if (index !== -1) {
				state.rawAnnouncements.splice(index, 1, {
					...updatedAnnouncement,
					show_until: updatedAnnouncement.show_until ? moment(updatedAnnouncement.show_until) : null
				})
			}
		},
		addAnnouncement(state, newAnnouncement) {
			state.rawAnnouncements.push({
				...newAnnouncement,
				show_until: newAnnouncement.show_until ? moment(newAnnouncement.show_until) : null
			})
		}
	},
	actions: {
		// dismiss announcement by saving into localStorage
		dismissAnnouncement({ state }, announcement) {
			// Prevent duplicate dismissals
			if (!state.dismissedAnnouncements.includes(announcement.id)) {
				state.dismissedAnnouncements.push(announcement.id)
				localStorage.setItem('dismissedAnnouncements', JSON.stringify(state.dismissedAnnouncements))
			}
		},
		async 'api::announcement.created_or_updated'({ state, commit }, announcement) {
			const exists = state.rawAnnouncements.some(a => a.id === announcement.id)
			
			if (exists) {
				commit('updateAnnouncement', announcement)
			} else {
				commit('addAnnouncement', announcement)
			}
		}
	}
}

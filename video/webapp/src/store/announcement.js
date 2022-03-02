// TODO sync dismissed announcements between tabs

import Vue from 'vue'
import moment from 'moment'

export default {
	namespaced: true,
	state: {
		rawAnnouncements: [],
		dismissedAnnouncements: localStorage.dismissedAnnouncements ? JSON.parse(localStorage.dismissedAnnouncements) : [],
	},
	getters: {
		announcements (state, getters, rootState) {
			return state.rawAnnouncements.map(announcement => {
				const showUntil = announcement.show_until ? moment(announcement.show_until) : null
				return Object.assign({}, announcement, {
					show_until: showUntil,
					expired: showUntil?.isBefore(rootState.now)
				})
			})
		},
		visibleAnnouncements (state, getters, rootState) {
			return getters.announcements.filter(announcement => announcement.state === 'active' && !announcement.expired && !state.dismissedAnnouncements.includes(announcement.id))
		}
	},
	mutations: {
		setAnnouncements (state, announcements) {
			for (const announcement of announcements) {
				if (announcement.show_until) announcement.show_until = moment(announcement.show_until)
			}
			state.rawAnnouncements = announcements
		}
	},
	actions: {
		// dismiss announcement by saving into localStorage
		dismissAnnouncement ({ state }, announcement) {
			state.dismissedAnnouncements.push(announcement.id)
			localStorage.setItem('dismissedAnnouncements', JSON.stringify(state.dismissedAnnouncements))
		},
		async 'api::announcement.created_or_updated' ({state}, announcement) {
			const existingAnnouncement = state.rawAnnouncements.find(a => a.id === announcement.id)
			if (existingAnnouncement) {
				for (let [key, value] of Object.entries(announcement)) {
					if (key === 'show_until' && value) value = moment(value)
					Vue.set(existingAnnouncement, key, value)
				}
			} else {
				state.rawAnnouncements.push(announcement)
			}
		}
	}
}

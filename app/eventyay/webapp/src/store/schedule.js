import moment from 'lib/timetravelMoment'
import api from 'lib/api'

export default {
	namespaced: true,
	state: {
		schedule: null,
		errorLoading: null,
		filter: {},
		now: moment(),
		currentLanguage: localStorage.getItem('userLanguage') || 'en'
	},
	getters: {
		favs(state, getters, rootState) {
			return rootState.user?.client_state?.schedule?.favs || []
		},
		pretalxScheduleUrl(state, getters, rootState) {
			if (!rootState.world.pretalx) {
				return ''
			}
			const pretalx = rootState.world.pretalx
			if (pretalx.url) {
				return pretalx.url
			}
			if (!pretalx.domain || !pretalx.event) return ''
			if (!pretalx.domain.endsWith('/')) {
				pretalx.domain += '/'
			}
			const url = new URL(`${pretalx.event}/schedule/widgets/schedule.json`, pretalx.domain)
			return url.toString()
		},
		pretalxApiBaseUrl(state, getters, rootState) {
			if (!rootState.world.pretalx?.domain || !rootState.world.pretalx?.event) return
			return rootState.world.pretalx.domain + 'api/events/' + rootState.world.pretalx.event
		},
		rooms(state, getters, rootState) {
			if (!state.schedule) return
			return state.schedule.rooms.map(room => rootState.rooms.find(r => r.pretalx_id === room.id) || room)
		},
		roomsLookup(state, getters) {
			if (!state.schedule) return {}
			return getters.rooms.reduce((acc, room) => {
				acc[room.pretalx_id || room.id] = room
				return acc
			}, {})
		},
		tracksLookup(state) {
			if (!state.schedule) return {}
			return state.schedule.tracks.reduce((acc, t) => { acc[t.id] = t; return acc }, {})
		},
		speakersLookup(state) {
			if (!state.schedule) return {}
			return state.schedule.speakers.reduce((acc, s) => { acc[s.code] = s; return acc }, {})
		},
		sessionTypeLookup(state) {
			if (!state.schedule) return {}
			return state.schedule.session_type.reduce((acc, s) => { acc[s.code] = s; return acc }, {})
		},
		sessions(state, getters, rootState) {
			if (!state.schedule) return
			const sessions = []
			const favArr = getters.favs || []
			for (const session of state.schedule.talks) {
				if (state.filter?.type === 'fav' && !favArr?.includes(session.code?.toString())) {
					continue
				} else if (state.filter?.type === 'track') {
					const { tracks } = state.filter
					if (tracks?.length && !tracks.includes(String(session.track))) {
						continue
					}
				}
				sessions.push({
					id: session.code ? session.code.toString() : null,
					title: session.title,
					abstract: session.abstract,
					url: session.url,
					start: moment.tz(session.start, rootState.userTimezone),
					end: moment.tz(session.end, rootState.userTimezone),
					speakers: session.speakers?.map(s => getters.speakersLookup[s]),
					track: getters.tracksLookup[session.track],
					room: getters.roomsLookup[session.room],
					tags: session.tags,
					session_type: session.session_type
				})
			}
			sessions.sort((a, b) => (
				// First sort by date, then by order of rooms
				a.start.diff(b.start) ||
				(state.schedule.rooms.findIndex((r) => r.id === a.room.id) - state.schedule.rooms.findIndex((r) => r.id === b.room.id))
			))
			return sessions
		},
		sessionsLookup(state, getters) {
			if (!state.schedule) return {}
			return getters.sessions.reduce((acc, s) => { acc[s.id] = s; return acc }, {})
		},
		days(state, getters) {
			if (!getters.sessions) return
			const days = []
			for (const session of getters.sessions) {
				if (days[days.length - 1] && days[days.length - 1].isSame(session.start, 'day')) continue
				days.push(session.start.clone().startOf('day'))
			}
			return days
		},
		sessionsScheduledNow(state, getters, rootState) {
			if (!getters.sessions) return
			const sessions = []
			for (const session of getters.sessions) {
				if (session.end.isBefore(rootState.now) || session.start.isAfter(rootState.now)) continue
				sessions.push(session)
			}
			return sessions
		},
		currentSessionPerRoom(state, getters, rootState) {
			if (!getters.sessions) return
			const rooms = {}
			for (const room of rootState.rooms) {
				if (room.schedule_data?.computeSession) {
					rooms[room.id] = {
						session: getters.sessionsScheduledNow.find(session => session.room === room)
					}
				} else if (room.schedule_data?.session) {
					rooms[room.id] = {
						session: state.sessions?.find(session => session.id === room.schedule_data.session)
					}
				}
			}
			return rooms
		},
		schedule(state) {
			return state.schedule
		},
		getSessionType: (state, getters) => (item) => {
			if (typeof item?.session_type === 'string') {
				return item.session_type
			} else if (typeof item?.session_type === 'object') {
				const sessionTypeKeys = Object.keys(item.session_type)
				const keyLanguage = sessionTypeKeys.find(key => key === state.currentLanguage) ||
					sessionTypeKeys.find(key => key === 'en') ||
					sessionTypeKeys[0]

				return item.session_type[keyLanguage]
			}
			return null
		},
		getSelectedName: (state, getters) => (item) => {
			if (typeof item?.name === 'string') {
				return item.name
			} else if (typeof item?.name === 'object') {
				const keys = Object.keys(item.name)
				const keyLanguage = keys.find(key => key === state.currentLanguage) ||
					keys.find(key => key === 'en') ||
					keys[0]

				return item.name[keyLanguage]
			}
			return null
		},
		filterSessionTypesByLanguage: (state, getters) => (data) => {
			const uniqueSessionTypes = new Set()

			data.forEach(item => {
				const sessionType = getters.getSessionType(item)
				if (sessionType) {
					uniqueSessionTypes.add(sessionType)
				}
			})

			return Array.from(uniqueSessionTypes).map(sessionType => ({
				value: sessionType,
				label: sessionType
			}))
		},
		filterItemsByLanguage: (state, getters) => (data) => {
			const languageMap = new Map()

			data.forEach(item => {
				const selectedName = getters.getSelectedName(item)
				if (selectedName) {
					languageMap.set(item.id, selectedName)
				}
			})

			return Array.from(languageMap).map(([id, name]) => ({ value: id, label: name }))
		},
		matchesSessionTypeFilter: (state) => (talk, selectedIds) => {
			if (typeof talk?.session_type === 'string') {
				return selectedIds.includes(talk.session_type)
			} else if (typeof talk?.session_type === 'object') {
				return Object.keys(talk.session_type).some(key => selectedIds.includes(talk.session_type[key]))
			}
			return false
		},
		filterTalk: (state, getter) => (refKey, selectedIds, previousResults) => {
			const talks = state.schedule.talks

			return talks
				.filter(talk => {
					const matchesSessionType = refKey === 'session_type' && getter.matchesSessionTypeFilter(talk, selectedIds)
					const matchesRefKey = selectedIds.includes(talk[refKey])

					return (matchesSessionType || matchesRefKey) && (!previousResults || previousResults.includes(talk.id))
				})
				.map(talk => talk.id) || []
		},
		filteredSessions: (state, getters) => (filter) => {
			let filteredResults = null

			Object.keys(filter).forEach(key => {
				const refKey = filter[key].refKey
				const selectedIds = filter[key].data
					.filter(item => item.selected)
					.map(item => item.value) || []

				if (selectedIds.length) {
					filteredResults = getters.filterTalk(refKey, selectedIds, filteredResults)
				}
			})

			return filteredResults
		}
	},
	actions: {
		async fetch({state, getters}) {
			// TODO error handling
			if (!getters.pretalxScheduleUrl) return
			// const version = await (await fetch(`${getters.pretalxApiBaseUrl}/schedules/`)).json()
			// console.log(version.results[0].version)
			try {
				state.errorLoading = null
				state.schedule = await (await fetch(getters.pretalxScheduleUrl)).json()
				state.schedule.session_type = state.schedule.talks.reduce((acc, current) => {
					const isDuplicate = acc.some(item => item.session_type === current.session_type)
					if (!isDuplicate) {
						acc.push(current)
					}
					return acc
				}, [])
			} catch (error) {
				state.errorLoading = error
			}
		},
		async fav({state, dispatch, rootState}, id) {
			let favs = rootState.user.client_state.schedule?.favs
			if (!favs) {
				favs = []
				rootState.user.client_state.schedule = {favs}
			}
			if (!favs.includes(id)) {
				favs.push(id)
				await dispatch('saveFavs', favs)
			}
		},
		async unfav({state, dispatch, rootState}, id) {
			let favs = rootState.user.client_state.schedule?.favs
			if (!favs) return
			rootState.user.client_state.schedule.favs = favs = favs.filter(fav => fav !== id)
			await dispatch('saveFavs', favs)
		},
		async saveFavs({rootState}, favs) {
			await api.call('user.update', {
				client_state: {
					...rootState.user.client_state,
					schedule: {
						favs: favs
					}
				}
			})
			// TODO error handling
		},
		setCurrentLanguage({commit}, language) {
			commit('setCurrentLanguage', language)
		},
		filter({ state }, filter) {
			state.filter = filter
		},
	},
	mutations: {
		setCurrentLanguage(state, language) {
			state.currentLanguage = language
		}
	}
}

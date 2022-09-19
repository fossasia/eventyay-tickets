import moment from 'lib/timetravelMoment'

export default {
	namespaced: true,
	state: {
		schedule: null,
		errorLoading: null
	},
	getters: {
		pretalxScheduleUrl (state, getters, rootState) {
			if (rootState.world.pretalx?.url) {
				return rootState.world.pretalx.url
			}
			if (!rootState.world.pretalx?.domain || !rootState.world.pretalx?.event) return
			if (!rootState.world.pretalx.domain.endsWith('/')) {
				rootState.world.pretalx.domain += '/'
			}
			return rootState.world.pretalx.domain + rootState.world.pretalx.event + '/schedule/widget/v2.json'
		},
		pretalxApiBaseUrl (state, getters, rootState) {
			if (!rootState.world.pretalx?.domain || !rootState.world.pretalx?.event) return
			return rootState.world.pretalx.domain + 'api/events/' + rootState.world.pretalx.event
		},
		roomsLookup (state, getters, rootState) {
			if (!state.schedule) return {}
			return state.schedule.rooms.reduce((acc, room) => {
				acc[room.id] = rootState.rooms.find(r => r.pretalx_id === room.id) || room
				return acc
			}, {})
		},
		tracksLookup (state) {
			if (!state.schedule) return {}
			return state.schedule.tracks.reduce((acc, t) => { acc[t.id] = t; return acc }, {})
		},
		speakersLookup (state) {
			if (!state.schedule) return {}
			return state.schedule.speakers.reduce((acc, s) => { acc[s.code] = s; return acc }, {})
		},
		sessions (state, getters, rootState) {
			if (!state.schedule) return
			const sessions = []
			for (const session of state.schedule.talks) {
				sessions.push({
					id: session.code ? session.code.toString() : null,
					title: session.title,
					abstract: session.abstract,
					url: session.url,
					start: moment.tz(session.start, rootState.userTimezone),
					end: moment.tz(session.end, rootState.userTimezone),
					speakers: session.speakers?.map(s => getters.speakersLookup[s]),
					track: getters.tracksLookup[session.track],
					room: getters.roomsLookup[session.room]
				})
			}
			sessions.sort((a, b) => (
				// First sort by date, then by order of rooms
				a.start.diff(b.start) ||
				(state.schedule.rooms.findIndex((r) => r.id === a.room.id) - state.schedule.rooms.findIndex((r) => r.id === b.room.id))
			))
			return sessions
		},
		sessionsLookup (state, getters) {
			if (!state.schedule) return {}
			return getters.sessions.reduce((acc, s) => { acc[s.id] = s; return acc }, {})
		},
		days (state, getters) {
			if (!getters.sessions) return
			const days = []
			for (const session of getters.sessions) {
				if (days[days.length - 1] && days[days.length - 1].isSame(session.start, 'day')) continue
				days.push(session.start.clone().startOf('day'))
			}
			return days
		},
		sessionsScheduledNow (state, getters, rootState) {
			if (!getters.sessions) return
			const sessions = []
			for (const session of getters.sessions) {
				if (session.end.isBefore(rootState.now) || session.start.isAfter(rootState.now)) continue
				sessions.push(session)
			}
			return sessions
		},
		currentSessionPerRoom (state, getters, rootState) {
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
		}
	},
	actions: {
		async fetch ({state, getters}) {
			// TODO error handling
			if (!getters.pretalxScheduleUrl) return
			// const version = await (await fetch(`${getters.pretalxApiBaseUrl}/schedules/`)).json()
			// console.log(version.results[0].version)
			try {
				state.schedule = await (await fetch(getters.pretalxScheduleUrl)).json()
			} catch (error) {
				state.errorLoading = error
			}
		},
	}
}

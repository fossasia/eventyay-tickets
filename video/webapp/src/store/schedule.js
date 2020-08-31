import moment from 'lib/timetravelMoment'

export default {
	namespaced: true,
	state: {
		schedule: null,
		now: moment(),

	},
	getters: {
		pretalxScheduleUrl (state, getters, rootState) {
			if (!rootState.world.pretalx?.domain || !rootState.world.pretalx?.event) return
			if (!rootState.world.pretalx.domain.endsWith('/')) {
				rootState.world.pretalx.domain += '/'
			}
			if (rootState.world.pretalx.event.includes('.json')) {
				return rootState.world.pretalx.domain + rootState.world.pretalx.event
			}
			return rootState.world.pretalx.domain + rootState.world.pretalx.event + '/schedule/widget/v2.json'
		},
		pretalxApiBaseUrl (state, getters, rootState) {
			if (!rootState.world.pretalx?.domain || !rootState.world.pretalx?.event) return
			if (rootState.world.pretalx.event.includes('.json')) {
				return
			}
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
		sessions (state, getters) {
			if (!state.schedule) return
			const sessions = []
			for (const session of state.schedule.talks) {
				sessions.push({
					id: session.code ? session.code.toString() : null,
					title: session.title,
					abstract: session.abstract,
					url: session.url,
					start: moment(session.start),
					end: moment(session.end),
					speakers: session.speakers?.map(s => getters.speakersLookup[s]),
					track: getters.tracksLookup[session.track],
					room: getters.roomsLookup[session.room]
				})
			}
			sessions.sort((a, b) => a.start.diff(b.start))
			return sessions
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
		sessionsScheduledNow (state, getters) {
			if (!getters.sessions) return
			const sessions = []
			for (const session of getters.sessions) {
				if (session.end.isBefore(state.now) || session.start.isAfter(state.now)) continue
				sessions.push(session)
			}
			return sessions
		},
	},
	mutations: {
		updateNow (state) {
			state.now = moment()
		}
	},
	actions: {
		async fetch ({state, getters}) {
			// TODO error handling
			if (!getters.pretalxScheduleUrl) return
			// const version = await (await fetch(`${getters.pretalxApiBaseUrl}/schedules/`)).json()
			// console.log(version.results[0].version)
			state.schedule = await (await fetch(getters.pretalxScheduleUrl)).json()
		},
	}
}

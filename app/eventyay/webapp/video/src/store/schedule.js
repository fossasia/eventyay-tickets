import moment from 'lib/timetravelMoment'
import config from '../../config'

// Thin adapter: loads schedule data and provides enriched sessions.
// Filtering/export/timezone are handled by the shared ScheduleView/ScheduleToolbar.
// Favs use localStorage with event-scoped key to stay in sync with the agenda side.

function getFavStorageKey (userCode = null) {
	const slug = window.eventyay?.eventSlug
	if (slug) return userCode ? `${slug}_${userCode}_favs` : `${slug}_favs`
	// Fallback: extract event slug from basePath (e.g. /org/event/video)
	const basePath = window.eventyay?.basePath || ''
	const segments = basePath.split('/').filter(s => s.length > 0 && s !== 'video')
	const eventSlug = segments[segments.length - 1] || ''
	if (!eventSlug) return 'schedule_favs'
	return userCode ? `${eventSlug}_${userCode}_favs` : `${eventSlug}_favs`
}

function loadFavsFromStorage (userCode = null) {
	try {
		return JSON.parse(localStorage.getItem(getFavStorageKey(userCode))) || []
	} catch {
		return []
	}
}

function saveFavsToStorage (favs, userCode = null) {
	localStorage.setItem(getFavStorageKey(userCode), JSON.stringify(favs))
}

function getCurrentUserCode (rootState) {
	return rootState.user?.pretalx_id ?? rootState.user?.code ?? rootState.user?.id ?? null
}

function getCsrfToken () {
	const match = document.cookie.match(/eventyay_csrftoken=([^;]+)/)
	return match ? match[1] : null
}

function getApiBase () {
	return config?.api?.base || ''
}

function getScheduleWidgetUrls () {
	const eventUrl = window.eventyay?.eventUrl || ''
	if (!eventUrl) return []
	const base = eventUrl.endsWith('/') ? eventUrl : `${eventUrl}/`
	const version = window.eventyay?.scheduleMeta?.version
	const versionPath = version ? `v/${encodeURIComponent(version)}/` : ''
	return [
		`${base}schedule/${versionPath}widgets/schedule.json?enrich=1`,
		`${base}schedule/${versionPath}widget/v2.json?enrich=1`,
	]
}

async function fetchVideoSchedule () {
	for (const url of getScheduleWidgetUrls()) {
		let response
		try {
			response = await fetch(url, { credentials: 'same-origin' })
		} catch {
			continue
		}
		if (response.status === 404) return null
		if (!response.ok) continue
		try {
			const data = await response.json()
			if (data?.schedule_unavailable) return null
			return data
		} catch {
			continue
		}
	}
	return null
}

// Listen for cross-tab localStorage changes so favs stay in sync when the
// user stars/unstars sessions in the schedule (agenda) tab.
let _storageListenerBound = false
function bindStorageListener (state) {
	if (_storageListenerBound) return
	_storageListenerBound = true
	window.addEventListener('storage', (e) => {
		const key = getFavStorageKey(state._favUserCode)
		if (e.key !== key) return
		if (e.newValue === null) {
			state.favs = []
			return
		}
		try {
			state.favs = JSON.parse(e.newValue) || []
		} catch { /* ignore malformed data */ }
	})
}

export default {
	namespaced: true,
	state: {
		schedule: null,
		scheduleMeta: null,
		scheduleLoaded: false,
		errorLoading: null,
		now: moment(),
		currentLanguage: localStorage.getItem('userLanguage') || 'en',
		favs: []
	},
	getters: {
		favs (state) {
			return state.favs
		},
		rooms (state, getters, rootState) {
			if (!state.schedule) return
			const rootByPretalxId = new Map()
			for (const r of rootState.rooms || []) {
				if (r?.pretalx_id != null) rootByPretalxId.set(String(r.pretalx_id), r)
			}
			return state.schedule.rooms.map(room => rootByPretalxId.get(String(room.id)) || room)
		},
		roomsLookup (state, getters) {
			if (!state.schedule) return {}
			return getters.rooms.reduce((acc, room) => {
				acc[room.pretalx_id || room.id] = room
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
			const videoModuleTypes = ['livestream.native', 'livestream.youtube', 'call.bigbluebutton', 'call.janus', 'call.zoom', 'call.jitsi', 'call.loungemesh']
			const videoRooms = new Set((rootState.rooms || []).filter(r => r.modules?.some(m => videoModuleTypes.includes(m.type))).map(r => r.pretalx_id ? String(r.pretalx_id) : null).filter(Boolean))
			const sessions = []
			for (const session of state.schedule.talks) {
				const roomId = session.room ? String(session.room) : null
				sessions.push({
					id: session.code ? session.code.toString() : null,
					title: session.title,
					abstract: session.abstract,
					description: session.description,
					content_locale: session.content_locale,
					do_not_record: session.do_not_record,
					url: session.url,
					start: moment.tz(session.start, rootState.userTimezone),
					end: moment.tz(session.end, rootState.userTimezone),
					speakers: (session.speakers || []).map(s => getters.speakersLookup[s] || { code: s }).filter(Boolean),
					track: getters.tracksLookup[session.track],
					room: getters.roomsLookup[session.room],
					fav_count: session.fav_count,
					tags: session.tags,
					session_type: session.session_type,
					resources: session.resources,
					answers: session.answers,
					exporters: session.exporters,
					recording_iframe: session.recording_iframe,
					stream_url: session.stream_url || null,
					has_video_room: videoRooms.has(roomId),
					stream_type: session.stream_type
				})
			}
			const roomIndexLookup = new Map()
			// Index by the same key we use in roomsLookup (prefer pretalx_id if present).
			getters.rooms.forEach((r, i) => roomIndexLookup.set((r?.pretalx_id ?? r?.id), i))
			sessions.sort((a, b) => (
				a.start.diff(b.start) ||
				((roomIndexLookup.get(a.room?.pretalx_id ?? a.room?.id) ?? Infinity) - (roomIndexLookup.get(b.room?.pretalx_id ?? b.room?.id) ?? Infinity))
			))
			return sessions
		},
		sessionsLookup (state, getters) {
			if (!state.schedule) return {}
			return getters.sessions.reduce((acc, s) => { acc[s.id] = s; return acc }, {})
		},
		sessionsBySpeaker (state, getters) {
			if (!getters.sessions) return {}
			return getters.sessions.reduce((acc, session) => {
				(session.speakers || []).forEach((speaker) => {
					const code = typeof speaker === 'string' ? speaker : speaker?.code
					if (!code) return
					if (!acc[code]) acc[code] = []
					acc[code].push(session)
				})
				return acc
			}, {})
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
			const sessionByRoom = new Map()
			for (const s of getters.sessionsScheduledNow || []) {
				if (s.room && !sessionByRoom.has(s.room)) sessionByRoom.set(s.room, s)
			}
			const sessionsLookup = getters.sessionsLookup || {}
			for (const room of rootState.rooms || []) {
				if (room.schedule_data?.computeSession) {
					rooms[room.id] = { session: sessionByRoom.get(room) }
				} else if (room.schedule_data?.session) {
					rooms[room.id] = { session: sessionsLookup[room.schedule_data.session] }
				}
			}
			return rooms
		},
		schedule (state) {
			return state.schedule
		},
		exporters (state) {
			return state.scheduleMeta?.exporters || []
		},
		scheduleMetaData (state) {
			return state.scheduleMeta || {}
		},
		getSessionType: (state) => (item) => {
			if (typeof item?.session_type === 'string') {
				return item.session_type
			} else if (typeof item?.session_type === 'object') {
				const keys = Object.keys(item.session_type)
				const keyLanguage = keys.find(k => k === state.currentLanguage) ||
					keys.find(k => k === 'en') ||
					keys[0]
				return item.session_type[keyLanguage]
			}
			return null
		},
		getSelectedName: (state) => (item) => {
			if (typeof item?.name === 'string') {
				return item.name
			} else if (typeof item?.name === 'object') {
				const keys = Object.keys(item.name)
				const keyLanguage = keys.find(k => k === state.currentLanguage) ||
					keys.find(k => k === 'en') ||
					keys[0]
				return item.name[keyLanguage]
			}
			return null
		}
	},
	actions: {
		async fetch ({ commit, dispatch }) {
			try {
				commit('setScheduleLoaded', false)
				commit('setErrorLoading', null)
				if (window.eventyay?.schedule) {
					commit('setSchedule', window.eventyay.schedule)
				} else {
					const data = await fetchVideoSchedule()
					if (data) {
						commit('setSchedule', data)
					}
				}
				if (window.eventyay?.scheduleMeta) {
					commit('setScheduleMeta', window.eventyay.scheduleMeta)
				}
			} catch (error) {
				commit('setErrorLoading', error)
			} finally {
				commit('setScheduleLoaded', true)
			}
			// Load favourites from server / localStorage after schedule data is ready
			dispatch('loadFavs')
		},
		async fav ({ state, rootState }, id) {
			if (!state.favs.includes(id)) {
				state.favs.push(id)
				const userCode = getCurrentUserCode(rootState)
				saveFavsToStorage(state.favs, userCode)
			}
			const apiBase = getApiBase()
			if (apiBase && rootState.user) {
				try {
					const headers = { 'Content-Type': 'application/json' }
					const csrf = getCsrfToken()
					if (csrf) headers['X-CSRFToken'] = csrf
					await fetch(`${apiBase}submissions/${id}/favourite/`, {
						method: 'POST',
						headers,
						credentials: 'same-origin'
					})
				} catch (error) {
					console.error('Failed to save favourite: %s', error)
				}
			}
		},
		async unfav ({ state, rootState }, id) {
			state.favs = state.favs.filter(fav => fav !== id)
			const userCode = getCurrentUserCode(rootState)
			saveFavsToStorage(state.favs, userCode)
			const apiBase = getApiBase()
			if (apiBase && rootState.user) {
				try {
					const headers = { 'Content-Type': 'application/json' }
					const csrf = getCsrfToken()
					if (csrf) headers['X-CSRFToken'] = csrf
					await fetch(`${apiBase}submissions/${id}/favourite/`, {
						method: 'DELETE',
						headers,
						credentials: 'same-origin'
					})
				} catch (error) {
					console.error('Failed to remove favourite: %s', error)
				}
			}
		},
		async loadFavs ({ state, rootState }) {
			const userCode = getCurrentUserCode(rootState)
			state._favUserCode = userCode
			const localFavs = [...new Set([
				...loadFavsFromStorage(userCode),
				...loadFavsFromStorage(null),
			])]
			state.favs = localFavs
			// Keep favs in sync when the schedule tab updates localStorage
			bindStorageListener(state)
			const apiBase = getApiBase()
			if (apiBase && rootState.user) {
				try {
					const headers = { 'Content-Type': 'application/json' }
					const csrf = getCsrfToken()
					if (csrf) headers['X-CSRFToken'] = csrf
					const response = await fetch(`${apiBase}submissions/favourites/merge/`, {
						method: 'POST',
						headers,
						body: JSON.stringify(localFavs),
						credentials: 'same-origin'
					})
					if (response.ok) {
						const merged = await response.json()
						if (Array.isArray(merged)) {
							state.favs = merged
							saveFavsToStorage(merged, userCode)
							localStorage.removeItem(getFavStorageKey(null))
						}
					}
				} catch (error) {
					console.error('Failed to merge favourites: %s', error)
				}
			}
		},
		setCurrentLanguage ({ commit }, language) {
			commit('setCurrentLanguage', language)
		}
	},
	mutations: {
		setSchedule (state, schedule) {
			state.schedule = schedule
		},
		setScheduleMeta (state, scheduleMeta) {
			state.scheduleMeta = scheduleMeta
		},
		setScheduleLoaded (state, scheduleLoaded) {
			state.scheduleLoaded = scheduleLoaded
		},
		setErrorLoading (state, errorLoading) {
			state.errorLoading = errorLoading
		},
		setCurrentLanguage (state, language) {
			state.currentLanguage = language
		}
	}
}

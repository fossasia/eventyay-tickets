const api = {
	eventSlug: window.location.pathname.split("/")[3],
	http (verb, url, body) {
		var fullHeaders = {}
		fullHeaders['Content-Type'] = 'application/json'

		const options = {
			method: verb || 'GET',
			headers: fullHeaders,
			body: body && JSON.stringify(body),
			credentials: 'include',
		}
		return window
			.fetch(url, options)
			.then(response => {
				if (response.status === 204) {
					return Promise.resolve()
				}
				return response.json().then(json => {
					if (!response.ok) {
						return Promise.reject({ response, json })
					}
					return Promise.resolve(json)
				})
			})
			.catch(error => {
				return Promise.reject(error)
			})
	},
	getList (url) {
		// The API returns a paginated list of results, but we want to return a
		// single list of all results. The results are returned in the `results`
		// property of the response and the next page URL is in the `next` property.
		return api.http('GET', url, null).then(response => {
			if (response.next) {
				return api.getList(response.next).then(nextPage => {
					return response.results.concat(nextPage)
				})
			}
			return response.results
		})
	},
	fetchTalks (options) {
		options = options || {}
		let url = `/orga/event/${api.eventSlug}/schedule/api/talks/`
		if (window.location.search) {
			url += window.location.search + '&'
		} else {
			url += '?'
		}
		if (options.since) {
			url += `since=${encodeURIComponent(options.since)}&`
		}
		if (options.warnings) {
			url += 'warnings=true'
		}
		return api.http('GET', url, null)
	},
	fetchAvailabilities () {
		const url = `/orga/event/${api.eventSlug}/schedule/api/availabilities/`
		return api.http('GET', url, null)
	},
	fetchWarnings () {
		const url = `/orga/event/${api.eventSlug}/schedule/api/warnings/`
		return api.http('GET', url, null)
	},
	fetchRooms () {
		return api.getList(`/api/events/${api.eventSlug}/rooms`)
	},
	saveTalk (talk, {action = 'PATCH'} = {}) {
		// Only call from App.saveTalk, which knows which data to update
		var url = [
			window.location.protocol,
			'//',
			window.location.host,
			window.location.pathname,
			'api/talks/',
			talk.id ? (talk.id + '/') : '',
			window.location.search,
		].join('')
		return api.http(action, url, {
			room: (talk.room && talk.room.id) ? talk.room.id : talk.room,
			start: talk.start,
			end: talk.end,
			duration: talk.duration,
			title: talk.title,
			description: talk.description,
		})
	},
	deleteTalk (talk) {
		return api.saveTalk({id: talk.id}, {action: 'DELETE'})
	},
	createTalk (talk) {
		return api.saveTalk(talk, {action: 'POST'})
	}
}
export default api

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
	fetchTalks (options) {
		options = options || {}
		var url = [
			// window.location.protocol,
			// "//",
			// window.location.host,
			// window.location.pathname,
			`/orga/event/${api.eventSlug}/schedule/api/talks/`
		].join('')
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
	fetchRooms () {
		const url = [
			// window.location.protocol,
			// "//",
			// window.location.host,
			// "/api/events/",
			// eventSlug,
			`/api/events/${api.eventSlug}/rooms`,
		].join('')
		return api.http('GET', url, null)
	},
	saveTalk (talk) {
		var url = [
			window.location.protocol,
			'//',
			window.location.host,
			window.location.pathname,
			'api/talks/',
			talk.id ? (talk.id + '/') : '',
			window.location.search,
		].join('')
		const action = talk.action || 'PATCH'
		return api.http(action, url, {
			room: (talk.room && talk.room.id) ? talk.room.id : talk.room,
			start: talk.start,
			action: talk.action,
			duration: talk.duration,
			description: talk.description,
		})
	},
	deleteTalk (talk) {
		return api.saveTalk({id: talk.id, action: 'DELETE'})
	},
	createTalk (talk) {
		talk.action = 'POST'
		return api.saveTalk(talk)
	}
}
export default api

import { apiErrorDetail, interpretationApiUrl, interpretationAuthHeaders } from './interpretation-api.js'
import { normalizeYoutubeVideoId, toYoutubeWatchUrl } from './validators.js'

export async function fetchInterpretationLanguageStreams(store, roomId) {
	const response = await fetch(interpretationApiUrl(store, roomId, 'streams/'), {
		headers: await interpretationAuthHeaders(),
		credentials: 'include',
	})
	const data = await response.json().catch(() => ({}))
	if (!response.ok) {
		throw new Error(apiErrorDetail(data) || 'Could not load interpretation language streams')
	}
	return data
}

export async function saveInterpretationLanguageStreams(store, roomId, languageStreams) {
	const response = await fetch(interpretationApiUrl(store, roomId, 'config/'), {
		method: 'PATCH',
		headers: await interpretationAuthHeaders(true),
		credentials: 'include',
		body: JSON.stringify({
			language_streams: (languageStreams || []).map(serializeLanguageStreamEntry),
		}),
	})
	const data = await response.json().catch(() => ({}))
	if (!response.ok) {
		throw new Error(apiErrorDetail(data) || 'Could not save interpretation language streams')
	}
	return data
}

export function cloneLanguageStreamEntries(entries) {
	return JSON.parse(JSON.stringify(entries || [])).map((entry) => {
		normalizeLanguageStreamEntry(entry)
		return entry
	})
}

export function serializeLanguageStreamEntry(entry) {
	if (!entry || typeof entry !== 'object') return entry
	const copy = { ...entry }
	const raw = [copy.url, copy.youtube_id]
		.map((value) => (value || '').trim())
		.find(Boolean) || ''
	if (!raw) {
		copy.url = ''
		copy.youtube_id = ''
		return copy
	}
	const ytId = normalizeYoutubeVideoId(raw)
	if (ytId) {
		copy.url = ytId
		copy.youtube_id = ytId
	} else {
		copy.url = raw
		copy.youtube_id = raw
	}
	return copy
}

export function normalizeLanguageStreamEntry(entry) {
	if (!entry) return
	const raw = [entry.url, entry.youtube_id]
		.map((value) => (value || '').trim())
		.find(Boolean) || ''
	if (!raw) {
		entry.url = ''
		if (entry.youtube_id == null) entry.youtube_id = ''
		return
	}
	const ytId = normalizeYoutubeVideoId(raw)
	if (ytId) {
		entry.youtube_id = ytId
		entry.url = toYoutubeWatchUrl(raw)
	} else {
		entry.url = raw
		entry.youtube_id = raw
	}
}

export function defaultLanguageStreamEntry() {
	return { language: '', url: '', youtube_id: '', use_video: false }
}

export async function syncInterpretationServices(store, roomId) {
	const response = await fetch(interpretationApiUrl(store, roomId, 'sync/'), {
		method: 'POST',
		headers: await interpretationAuthHeaders(),
		credentials: 'include',
	})
	const data = await response.json().catch(() => ({}))
	if (!response.ok) {
		throw new Error(apiErrorDetail(data) || 'Could not sync interpretation services')
	}
	return data
}

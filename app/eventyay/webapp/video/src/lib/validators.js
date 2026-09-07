/* globals ENV_DEVELOPMENT */
import {
	helpers,
	required as _required,
	maxLength as _maxLength,
	minLength as _minLength,
	email as _email,
	integer as _integer,
	maxValue as _maxValue,
	minValue as _minValue,
	url as _url
} from '@vuelidate/validators/dist/raw.mjs'

// Keep function names and export style as in main branch
export function required(message) {
	return helpers.withMessage(message, _required)
}
export function email(message) {
	return helpers.withMessage(message, _email)
}
export function maxLength(length, message) {
	return helpers.withMessage(message, _maxLength(length))
}
export function minLength(length, message) {
	return helpers.withMessage(message, _minLength(length))
}
export function integer(message) {
	return helpers.withMessage(message, _integer)
}
export function maxValue(maxVal, message) {
	return helpers.withMessage(message, _maxValue(maxVal))
}
export function minValue(minVal, message) {
	return helpers.withMessage(message, _minValue(minVal))
}
export function color(message) {
	return helpers.withMessage(message, helpers.regex(/^#([a-zA-Z0-9]{3}|[a-zA-Z0-9]{6})$/))
}

// Accepts a raw 11-character YouTube video ID or common YouTube URL formats and
// returns the normalized ID. Returns null when no valid ID can be extracted.
export function normalizeYoutubeVideoId(input) {
	if (input === null || input === undefined) return null
	const raw = String(input).trim()
	if (!raw) return null

	// If user already entered an ID, keep it.
	const directId = raw.match(/^[0-9A-Za-z_-]{11}$/)
	if (directId) return raw

	// Allow protocol-less inputs like youtu.be/ID or youtube.com/watch?v=ID
	let s = raw
	if (/^(?:www\.)?(?:youtube\.com|youtube-nocookie\.com|youtu\.be)\//i.test(s)) {
		s = `https://${s}`
	}

	// Parse as URL when possible and extract from known locations.
	try {
		const url = new URL(s)
		const host = url.hostname.replace(/^www\./, '').toLowerCase()

		// youtu.be/<id>
		if (host === 'youtu.be') {
			const id = url.pathname.split('/').filter(Boolean)[0]
			if (id && /^[0-9A-Za-z_-]{11}$/.test(id)) return id
		}

		// youtube.com/watch?v=<id>
		const v = url.searchParams.get('v')
		if (v && /^[0-9A-Za-z_-]{11}$/.test(v)) return v

		// youtube.com/embed/<id>, /shorts/<id>, /live/<id>, /v/<id>
		const pathMatch = url.pathname.match(/^\/(?:embed|shorts|live|v)\/([0-9A-Za-z_-]{11})(?:[?/]|$)/)
		if (pathMatch) return pathMatch[1]
	} catch (e) {
		// Fall back to regex extraction below.
	}

	// Last resort: search for an 11-char id after typical markers.
	const m = raw.match(/(?:youtu\.be\/|v=|\/embed\/|\/shorts\/|\/live\/|\/v\/)([0-9A-Za-z_-]{11})/)
	if (m) return m[1]

	return null
}

// Expand a raw YouTube ID into a watch URL so form fields show a URL on load,
// not only after the user focuses/blurs the input.
export function toYoutubeWatchUrl(input) {
	if (input === null || input === undefined) return ''
	const raw = String(input).trim()
	if (!raw) return ''
	const id = normalizeYoutubeVideoId(raw)
	if (!id) return raw
	if (/^https?:\/\//i.test(raw)) return raw
	return `https://www.youtube.com/watch?v=${id}`
}

export function normalizeAudioTranslationSource(audioSource) {
	if (!audioSource) return null
	const youtubeId = normalizeYoutubeVideoId(audioSource)
	if (youtubeId) return youtubeId
	try {
		new URL(audioSource)
		return audioSource
	} catch (e) {
		return null
	}
}

export function isUsableAudioTranslationEntry(entry) {
	if (!entry?.language) return false
	if (entry.language === 'Original') return true
	return !!normalizeAudioTranslationSource(entry.url || entry.youtube_id)
}

export function youtubeid(message) {
	return helpers.withMessage(message, (value) => {
		// Keep required-ness separate: empty is valid here.
		if (!helpers.req(value)) return true
		return !!normalizeYoutubeVideoId(value)
	})
}
const relative = helpers.regex(/^\/.*$/)
const devurl = helpers.regex(/^http:\/\/localhost.*$/) // vuelidate does not allow localhost
export function url(message) {
	return helpers.withMessage(message, (value) => (!helpers.req(value) || _url(value) || relative(value) || (ENV_DEVELOPMENT && devurl(value))))
}
export function isJson(message = 'Invalid JSON') {
	return helpers.withMessage(message, (value) => {
		if (value == null || !String(value).trim()) return true
		try {
			JSON.parse(value)
			return true
		} catch (e) {
			return false
		}
	})
}

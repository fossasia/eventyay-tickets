import { isUsableAudioTranslationEntry } from './lib/validators.js'

const ORIGINAL_LANGUAGE = 'Original'

export function roomUsesPluginLanguageStreams(room) {
	return Boolean(room?.interpretation_use_plugin_streams)
}

function ensureOriginalLanguageEntry(languages) {
	const list = Array.isArray(languages) ? [...languages] : []
	if (!list.some(entry => entry?.language === ORIGINAL_LANGUAGE)) {
		list.unshift({ language: ORIGINAL_LANGUAGE, url: null, youtube_id: null, use_video: false })
	}
	return list
}

export function pluginLanguageStreams(room) {
	if (!roomUsesPluginLanguageStreams(room)) {
		return []
	}
	const streams = room?.interpretation_language_streams
	const usable = Array.isArray(streams)
		? streams.filter(entry => isUsableAudioTranslationEntry(entry))
		: []

	const uniqueStreams = []
	const seenKeys = new Set()

	for (const entry of usable) {
		// Create a unique key based on the stream's primary identifiers
		const key = `${entry.language}:${entry.tts_ws_url || ''}:${entry.whep_url || entry.whip_url || ''}:${entry.url || entry.youtube_id || ''}`
		if (!seenKeys.has(key)) {
			seenKeys.add(key)
			uniqueStreams.push(entry)
		}
	}

	return ensureOriginalLanguageEntry(uniqueStreams)
}

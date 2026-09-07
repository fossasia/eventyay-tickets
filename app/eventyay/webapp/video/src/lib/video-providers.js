import { isRoomTypeAvailable } from './room-type-permissions.js'

export const VIDEO_CREATE_PROVIDERS = [
	{
		id: 'stream',
		roomTypeId: 'stage',
		label: 'Stream (YT, HLS)',
		roomKind: 'Stage',
		shortLabel: 'Stream',
		icon: 'theater',
		description: 'Present a live HLS or YouTube stream, optionally with chat and Q&A.',
		featureFlag: null
	},
	{
		id: 'bbb',
		roomTypeId: 'channel-bbb',
		label: 'BBB',
		roomKind: 'Video Channel',
		shortLabel: 'BBB',
		icon: 'webcam',
		description: 'Connect attendees in real time for workshops or panels powered by BigBlueButton.',
		featureFlag: null
	},
	{
		id: 'zoom',
		roomTypeId: 'channel-zoom',
		label: 'Zoom',
		roomKind: 'Video Channel',
		shortLabel: 'Zoom',
		icon: 'webcam',
		description: 'Embed a Zoom meeting or webinar directly into eventyay.',
		featureFlag: null
	},
	{
		id: 'jitsi',
		roomTypeId: 'channel-jitsi',
		label: 'Jitsi',
		roomKind: 'Video Channel',
		shortLabel: 'Jitsi',
		icon: 'webcam',
		description: 'Connect attendees through a Jitsi meeting.',
		featureFlag: 'jitsi'
	},
	{
		id: 'janus',
		roomTypeId: 'channel-janus',
		label: 'Janus',
		roomKind: 'Video Channel',
		shortLabel: 'Janus',
		icon: 'webcam',
		description: 'Connect attendees in real time for workshops or panels powered by Janus.',
		featureFlag: 'janus'
	},
	{
		id: 'loungemesh',
		roomTypeId: 'channel-loungemesh',
		label: 'LoungeMesh',
		roomKind: 'Video Channel',
		shortLabel: 'LoungeMesh',
		icon: 'webcam',
		description: 'Spatial proximity networking and workshop lounge powered by LoungeMesh.',
		featureFlag: null
	}
]

export const MODULE_TYPE_TO_PROVIDER = {
	'call.bigbluebutton': 'bbb',
	'call.jitsi': 'jitsi',
	'call.janus': 'janus',
	'call.loungemesh': 'loungemesh',
	'call.zoom': 'zoom',
	'networking.roulette': 'janus'
}

export function isVideoProviderEnabled(provider, isFeatureEnabled, videoProvidersConfig) {
	if (videoProvidersConfig && videoProvidersConfig[provider.id]) {
		if (videoProvidersConfig[provider.id].organizer === false) {
			return false
		}
	}
	return !provider.featureFlag || Boolean(isFeatureEnabled ? isFeatureEnabled(provider.featureFlag) : true)
}

export function isVideoProviderPermitted(provider, hasPermission, isAdminMode = false) {
	if (isRoomTypeAvailable(provider.roomTypeId, hasPermission, isAdminMode)) {
		return true
	}
	// Rooms admin users with room:update can still create Stream rooms without the
	// dedicated stage-create permission. Server-backed providers stay admin-gated.
	return provider.roomTypeId === 'stage' && hasPermission('room:update')
}

export function getAvailableVideoProviders(hasPermission, isAdminMode, isFeatureEnabled, videoProvidersConfig) {
	return VIDEO_CREATE_PROVIDERS.filter(provider =>
		isVideoProviderEnabled(provider, isFeatureEnabled, videoProvidersConfig) &&
		isVideoProviderPermitted(provider, hasPermission, isAdminMode)
	)
}

export function isRoomVisibleToAttendee(room, videoProvidersConfig) {
	if (!videoProvidersConfig) return true
	const modules = room?.modules || room?.module_config || []
	for (const m of modules) {
		const type = typeof m === 'string' ? m : m?.type
		const provider = MODULE_TYPE_TO_PROVIDER[type]
		if (provider && videoProvidersConfig[provider]?.attendee === false) {
			return false
		}
	}
	return true
}

export function getVideoProviderByRoomTypeId(roomTypeId) {
	return VIDEO_CREATE_PROVIDERS.find(provider => provider.roomTypeId === roomTypeId) || null
}

export function getConfiguredRoomLabel(type) {
	if (!type) return ''
	const provider = getVideoProviderByRoomTypeId(type.id)
	if (provider) return `${provider.roomKind}: ${provider.shortLabel}`
	if (type.id === 'channel-zoom') return 'Video Channel: Zoom'
	if (type.id === 'channel-loungemesh') return 'Video Channel: LoungeMesh'
	return type.name
}

export function getVideoProviderStartingConfig(type) {
	if (type?.id === 'stage') {
		return { playback_mode: 'always_on' }
	}
	if (type?.id === 'channel-bbb') {
		return {
			record: false,
			hide_presentation: false,
			waiting_room: false,
			auto_microphone: false,
			auto_camera: false,
			bbb_mute_on_start: false,
			bbb_disable_cam: false,
			bbb_disable_chat: false
		}
	}
	if (type?.id === 'channel-zoom') {
		return {
			meeting_number: '',
			password: '',
			disable_chat: false
		}
	}
	if (type?.id === 'channel-jitsi') {
		return {
			prefer_server: '',
			start_with_audio_muted: false,
			start_with_video_muted: false,
			waiting_room: false,
			record: false,
			livestreaming: false,
			disable_cam: false,
			disable_chat: false,
			require_display_name: false
		}
	}
	if (type?.id === 'channel-janus') {
		return {
			prefer_server: '',
			start_with_audio_muted: false,
			start_with_video_muted: false,
			waiting_room: false,
			disable_cam: false,
			disable_chat: false
		}
	}
	if (type?.id === 'channel-loungemesh') {
		return {
			prefer_server: '',
			enable_notes: true,
			enable_whiteboard: true,
			enable_spatial_chat: true
		}
	}
	return {}
}

export function applyVideoProviderToConfig(config, type) {
	if (!config || !type) return false
	const moduleConfig = [{
		type: type.startingModule,
		config: getVideoProviderStartingConfig(type)
	}]
	if (type.id === 'channel-zoom') {
		moduleConfig.push({
			type: 'chat.native',
			config: { volatile: true }
		})
	}
	config.module_config = moduleConfig
	return true
}

export function canManageVideoRooms(hasPermission) {
	return hasPermission('room:update')
}

export const EMBEDDED_SUITE_MODULE_TYPES = [
	'call.bigbluebutton',
	'call.jitsi'
]

export function hasEmbeddedSuite(modules) {
	if (!modules) return false
	if (Array.isArray(modules)) {
		return modules.some(m => EMBEDDED_SUITE_MODULE_TYPES.includes(m?.type || m))
	}
	return EMBEDDED_SUITE_MODULE_TYPES.some(type => Boolean(modules[type]))
}

export function supportsPlatformSidebar(modules) {
	if (!modules) return false
	if (hasEmbeddedSuite(modules)) return false
	if (Array.isArray(modules)) {
		if (modules.length === 1 && modules[0]?.type === 'chat.native') return false
		return modules.some(m => ['chat.native', 'question', 'poll'].includes(m?.type))
	}
	if (modules['chat.native'] && Object.keys(modules).length === 1) return false
	return Boolean(modules['chat.native'] || modules.question || modules.poll)
}

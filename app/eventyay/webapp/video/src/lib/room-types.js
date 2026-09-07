import features from 'features'

const ROOM_TYPES = [{
	id: 'stage',
	icon: 'theater',
	name: 'Stage',
	description: 'A stage allows you to present a live stream to your audience, optionally combined with chat and Q&A features.',
	startingModule: 'livestream.native',
	inferModules: ['livestream.native', 'livestream.youtube', 'livestream.iframe']
}, {
	id: 'channel-bbb',
	icon: 'webcam',
	name: 'Video Channel',
	description: 'A video channel allows you to connect with attendees in real time and host workshops or panels. The video channels are powered by BigBlueButton and support 25-80 people, depending on usage.',
	startingModule: 'call.bigbluebutton',
	videoChannel: true
}, {
	id: 'channel-janus',
	icon: 'webcam',
	name: 'Video Channel (beta)',
	description: 'A video channel allows you to connect with attendees in real time and host workshops or panels. The video channels are powered by Janus.',
	startingModule: 'call.janus',
	videoChannel: true,
	behindFeatureFlag: 'janus'
}, {
	id: 'channel-zoom',
	icon: 'webcam',
	name: 'Video Channel (Zoom)',
	description: 'This room type allows you to embed a Zoom meeting or webinar directly into eventyay.',
	startingModule: 'call.zoom',
	videoChannel: true,
	behindFeatureFlag: 'zoom'
}, {
	id: 'channel-jitsi',
	icon: 'webcam',
	name: 'Video Channel (Jitsi)',
	description: 'This room type allows you to connect with attendees through a Jitsi meeting.',
	startingModule: 'call.jitsi',
	videoChannel: true,
	behindFeatureFlag: 'jitsi'
}, {
	id: 'channel-text',
	icon: 'pound',
	name: 'Chat Channel',
	description: 'A chat channel for text communication between attendees. Managed separately from rooms.',
	startingModule: 'chat.native',
	managementArea: 'chat'
}, {
	id: 'channel-roulette',
	icon: 'webcam',
	name: 'Random video calls',
	description: 'Connect your attendees for short video calls in random combinations.',
	startingModule: 'networking.roulette',
	inferModules: ['networking.roulette'],
	sidebarGroup: 'networking',
	behindFeatureFlag: 'roulette'
}, {
	id: 'page-landing',
	icon: 'text-box-outline',
	name: 'Landing Page',
	description: 'The landing place module combines the most important content into one place for your attendees to see after they join.',
	startingModule: 'page.landing',
	behindFeatureFlag: 'page.landing'
}]

export const VIDEO_CHANNEL_MODULE_TYPES = new Set(ROOM_TYPES.filter(type => type.videoChannel).map(type => type.startingModule))
export const NETWORKING_MODULE_TYPES = new Set(ROOM_TYPES.filter(type => type.sidebarGroup === 'networking').map(type => type.startingModule))
export const CHAT_CHANNEL_TYPE_ID = 'channel-text'

export function isChatChannel(roomOrConfig) {
	const modules = roomOrConfig?.module_config || roomOrConfig?.modules || []
	if (!Array.isArray(modules) || !modules.length) return false
	return modules.some(m => m.type === 'chat.native') && !modules.some(m => ['livestream.native', 'livestream.youtube', 'call.bigbluebutton', 'call.janus', 'call.zoom', 'call.jitsi', 'networking.roulette', 'page.landing'].includes(m.type))
}

export function isChatManagedRoom(roomOrConfig) {
	return isChatChannel(roomOrConfig)
}

export function mergeReorderedIds(allIds, subsetOrder) {
	const subset = new Set(subsetOrder.map(String))
	const queue = subsetOrder.map(String)
	return allIds.map(id => subset.has(String(id)) ? queue.shift() : String(id))
}

export default ROOM_TYPES.filter(type => !type.behindFeatureFlag || features.enabled(type.behindFeatureFlag))

export function getRoomTypeById(id) {
	return ROOM_TYPES.find(type => type.id === id) || null
}

export function localizeRoomType(t, type) {
	if (!type) return type
	const labels = {
		stage: {
			name: t('Stage'),
			description: t('A stage allows you to present a live stream to your audience, optionally combined with chat and Q&A features.'),
		},
		'channel-bbb': {
			name: t('Video Channel'),
			description: t('A video channel allows you to connect with attendees in real time and host workshops or panels. The video channels are powered by BigBlueButton and support 25-80 people, depending on usage.'),
		},
		'channel-janus': {
			name: t('Video Channel (beta)'),
			description: t('A video channel allows you to connect with attendees in real time and host workshops or panels. The video channels are powered by Janus.'),
		},
		'channel-zoom': {
			name: t('Video Channel (Zoom)'),
			description: t('This room type allows you to embed a Zoom meeting or webinar directly into eventyay.'),
		},
		'channel-jitsi': {
			name: t('Video Channel (Jitsi)'),
			description: t('This room type allows you to connect with attendees through a Jitsi meeting.'),
		},
		'channel-text': {
			name: t('Chat Channel'),
			description: t('A chat channel for text communication between attendees. Managed separately from rooms.'),
		},
		'channel-roulette': {
			name: t('Random video calls'),
			description: t('Connect your attendees for short video calls in random combinations.'),
		},
		'page-landing': {
			name: t('Landing Page'),
			description: t('The landing place module combines the most important content into one place for your attendees to see after they join.'),
		},
	}
	const localized = labels[type.id]
	if (!localized) return type
	return { ...type, ...localized }
}

export function inferType(config) {
	if (!config) return
	const moduleConfig = Array.isArray(config.module_config) ? config.module_config : []
	const modules = moduleConfig.reduce((acc, module) => {
		acc[module.type] = module
		return acc
	}, {})
	const findByModule = module => ROOM_TYPES.find(type => type.startingModule === module)

	// infer media rooms by primary content
	const mediaRoomType = ROOM_TYPES.find(type => (type.inferModules || (type.videoChannel ? [type.startingModule] : [])).some(module => modules[module]))
	if (mediaRoomType) return mediaRoomType

	// non-media rooms should only have one module
	if (moduleConfig.length === 1) {
		return findByModule(moduleConfig[0].type)
	}
}

// TODO clean up with `inferType` function
export function inferRoomType(room) {
	return inferType({module_config: room.modules})
}

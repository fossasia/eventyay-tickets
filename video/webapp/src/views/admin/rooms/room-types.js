import features from 'features'

const ROOM_TYPES = [{
	id: 'stage',
	icon: 'theater',
	name: 'Stage',
	description: 'livestream und so',
	startingModule: 'livestream.native'
}, {
	id: 'channel-text',
	icon: 'pound',
	name: 'Text Channel',
	description: 'livestream und so',
	startingModule: 'chat.native'
}, {
	id: 'channel-bbb',
	icon: 'webcam',
	name: 'Video Channel',
	description: 'livestream und so',
	startingModule: 'call.bigbluebutton'
}, {
	id: 'channel-janus',
	icon: 'webcam',
	name: 'Janus Video Channel',
	description: 'livestream und so',
	startingModule: 'call.janus',
	behindFeatureFlag: 'janus'
}, {
	id: 'channel-zoom',
	icon: 'webcam',
	name: 'Zoom Video Channel',
	description: 'zoomzoom',
	startingModule: 'call.zoom',
	behindFeatureFlag: 'zoom'
}, {
	id: 'exhibition',
	icon: 'domain',
	name: 'Exhibition',
	description: 'Shilling Stands',
	startingModule: 'exhibition.native'
}, {
	id: 'channel-roulette',
	icon: 'webcam',
	name: 'Chat Roulette',
	description: 'meet randos',
	startingModule: 'networking.roulette',
	behindFeatureFlag: 'roulette'
}, {
	id: 'page-static',
	icon: 'text-box-outline',
	name: 'Page',
	description: 'static stuff',
	startingModule: 'page.static'
}, {
	id: 'page-iframe',
	icon: 'text-box-outline',
	name: 'IFrame',
	description: 'arbitrary interwebs',
	startingModule: 'page.iframe'
}, {
	id: 'page-landing',
	icon: 'text-box-outline',
	name: 'Landing Page',
	description: 'LAAAND',
	startingModule: 'page.landing',
	behindFeatureFlag: 'page.landing'
}]

export default ROOM_TYPES.filter(type => !type.behindFeatureFlag || features.enabled(type.behindFeatureFlag))

export function inferType (config) {
	const modules = config.module_config.reduce((acc, module) => {
		acc[module.type] = module
		return acc
	}, {})
	const find = id => ROOM_TYPES.find(type => type.id === id)
	if (modules['livestream.native'] || modules['livestream.youtube']) return find('stage')
	if (modules['page.static']) return find('page-static')
	if (modules['page.iframe']) return find('page-iframe')
	if (modules['call.bigbluebutton']) return find('channel-bbb')
	if (modules['call.zoom']) return find('channel-zoom')
	if (modules['chat.native']) return find('channel-text')
}

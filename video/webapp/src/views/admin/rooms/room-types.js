import features from 'features'

const ROOM_TYPES = [{
	id: 'stage',
	icon: 'theater',
	name: 'Stage',
	description: 'A stage allows you to present a live stream to your audience, optionally combined with chat and Q&A features.',
	startingModule: 'livestream.native'
}, {
	id: 'channel-bbb',
	icon: 'webcam',
	name: 'Video Channel',
	description: 'A video channel allows you to connect with attendees in real time and host workshops or panels. The video channels are powered by BigBlueButton and support 25-80 people, depending on usage.',
	startingModule: 'call.bigbluebutton'
}, {
	id: 'channel-janus',
	icon: 'webcam',
	name: 'Video Channel (beta)',
	description: 'A video channel allows you to connect with attendees in real time and host workshops or panels. The video channels are powered by Janus.',
	startingModule: 'call.janus',
	behindFeatureFlag: 'janus'
}, {
	id: 'channel-zoom',
	icon: 'webcam',
	name: 'Video Channel (Zoom)',
	description: 'This room type allows you to embed a zoom meeting or webinar directly into venueless.',
	startingModule: 'call.zoom',
	behindFeatureFlag: 'zoom'
}, {
	id: 'channel-text',
	icon: 'pound',
	name: 'Text Channel',
	description: 'This type of channel allows you to enable pure-text communication between your attendees.',
	startingModule: 'chat.native'
}, {
	id: 'exhibition',
	icon: 'domain',
	name: 'Exhibition',
	description: 'Using an exhibition room, sponsors or exhibitors can present themselves to your audience.',
	startingModule: 'exhibition.native'
}, {
	id: 'channel-roulette',
	icon: 'webcam',
	name: 'Random video calls',
	description: 'Connect your attendees for short video calls in random combinations.',
	startingModule: 'networking.roulette',
	behindFeatureFlag: 'roulette'
}, {
	id: 'page-static',
	icon: 'text-box-outline',
	name: 'Page',
	description: 'A page contains static content for your attendees.',
	startingModule: 'page.static'
}, {
	id: 'page-iframe',
	icon: 'text-box-outline',
	name: 'IFrame',
	description: 'Using IFrames, you can embed arbitrary web pages and web applications into venueless.',
	startingModule: 'page.iframe'
}, {
	id: 'page-landing',
	icon: 'text-box-outline',
	name: 'Landing Page',
	description: 'The landing place module combines the most important content into one place for your attendees to see after they join.',
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
	if (modules['call.janus']) return find('channel-janus')
	if (modules['call.zoom']) return find('channel-zoom')
	if (modules['chat.native']) return find('channel-text')
}

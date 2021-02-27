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
	id: 'channel-video',
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
	id: 'page.static',
	icon: 'text-box-outline',
	name: 'Page',
	description: 'static stuff',
	startingModule: 'page.static'
}, {
	id: 'page.iframe',
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

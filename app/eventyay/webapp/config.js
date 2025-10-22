/* global ENV_DEVELOPMENT */
import cloneDeep from 'lodash/cloneDeep'
let config
if (ENV_DEVELOPMENT || (!window.venueless && !window.eventyay)) {
	const { protocol, hostname, port, pathname } = window.location
	const wsProtocol = protocol === 'https:' ? 'wss' : 'ws'
	// Expect /video/<event_identifier>/...
	const segments = pathname.split('/').filter(Boolean)
	let eventIdentifier = segments[1] // segments[0] === 'video'
	if (!eventIdentifier) eventIdentifier = 'sample'
	const hostPort = port ? `${hostname}:${port}` : hostname
	config = {
		api: {
			base: `${protocol}//${hostPort}/api/v1/events/${eventIdentifier}/`,
			socket: `${wsProtocol}://${hostPort}/ws/event/${eventIdentifier}/`,
			upload: `${protocol}//${hostPort}/storage/${eventIdentifier}/upload/`,
			scheduleImport: `${protocol}//${hostPort}/storage/${eventIdentifier}/schedule_import/`,
			feedback: `${protocol}//${hostPort}/_feedback/`,
		},
		defaultLocale: 'en',
		locales: ['en', 'de', 'pt_BR', 'ar', 'fr', 'es', 'uk', 'ru'],
		// Mark that there is no theme endpoint so theme.js can skip fetch
		noThemeEndpoint: true,
		features: [],
		theme: {
			logo: {
				url: '/video/eventyay-video-logo.png',
				fitToWidth: false
			},
			colors: {
				primary: '#2185d0',
				sidebar: '#2185d0',
				bbb_background: '#ffffff',
			}
		},
		basePath: '/video'
	}
} else {
	// load from index.html as injected config: prefer window.eventyay (new) else fallback to legacy window.venueless
	const injected = window.eventyay || window.venueless
	config = cloneDeep(injected)
	// Normalize features to array for consumer convenience (feature flags object => enabled keys array)
	if (config.features && !Array.isArray(config.features)) {
		config.features = Object.keys(config.features).filter(k => config.features[k])
	}
}
export default config

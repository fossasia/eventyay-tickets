/* global ENV_DEVELOPMENT */
import cloneDeep from 'lodash/cloneDeep'
let config
if (ENV_DEVELOPMENT || !window.venueless) {
	const hostname = window.location.hostname
	const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
	const httpProtocol = window.location.protocol
	// Extract the world name from the URL path
	const pathSegments = window.location.pathname.split('/')
	const worldName = pathSegments.length > 2 ? pathSegments[2] : 'sample'
	config = {
		api: {
			base: `${httpProtocol}//${hostname}:8443/api/v1/worlds/${worldName}/`,
			socket: `${wsProtocol}://${hostname}:8443/ws/world/${worldName}/`,
			upload: `${httpProtocol}//${hostname}:8443/storage/${worldName}/upload/`,
			scheduleImport: `${httpProtocol}//${hostname}:8443/storage/${worldName}/schedule_import/`,
			feedback: `${httpProtocol}//${hostname}:8443/_feedback/`,
		},
		defaultLocale: 'en',
		locales: ['en', 'de', 'pt_BR', 'ar', 'fr', 'es', 'uk', 'ru'],
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
		basePath: '/video',
	}
} else {
	// load from index.html as `window.venueless = {…}`
	config = cloneDeep(window.venueless)
}
export default config

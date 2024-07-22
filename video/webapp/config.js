/* global ENV_DEVELOPMENT */
import cloneDeep from 'lodash/cloneDeep'
let config
if (ENV_DEVELOPMENT || !window.venueless) {
	const hostname = window.location.hostname
	const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
	const httpProtocol = window.location.protocol;
	config = {
		api: {
			base: `${httpProtocol}//${hostname}:8443/api/v1/worlds/sample/`,
			socket: `${wsProtocol}://${hostname}:8443/ws/world/sample/`,
			upload: `${httpProtocol}//${hostname}:8443/storage/upload/`,
			scheduleImport: `${httpProtocol}//${hostname}:8443/storage/schedule_import/`,
			feedback: `${httpProtocol}//${hostname}:8443/_feedback/`,
		},
		defaultLocale: 'en',
		locales: ['en', 'de', 'pt_BR'],
		theme: {
			logo: {
				url: "/eventyay-video-logo.svg",
                fitToWidth: false
			},
			colors: {
				primary: '#2185d0',
				sidebar: '#2185d0',
				bbb_background: '#ffffff',
			}
		}
	}
} else {
	// load from index.html as `window.venueless = {…}`
	config = cloneDeep(window.venueless)
}
export default config

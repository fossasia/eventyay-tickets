/* global ENV_DEVELOPMENT */
import cloneDeep from 'lodash/cloneDeep'
let config
if (ENV_DEVELOPMENT || !window.venueless) {
	const hostname = window.location.hostname
	const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
	config = {
		api: {
			base: `http://${hostname}:8443/api/v1/worlds/sample/`,
			socket: `${wsProtocol}://${hostname}:8443/ws/world/sample/`,
			upload: `http://${hostname}:8443/storage/upload/`,
			scheduleImport: `http://${hostname}:8443/storage/schedule_import/`,
			feedback: `http://${hostname}:8443/_feedback/`,
		},
		defaultLocale: 'en',
		locales: ['en', 'de', 'pt_BR'],
	}
} else {
	// load from index.html as `window.venueless = {…}`
	config = cloneDeep(window.venueless)
}
export default config

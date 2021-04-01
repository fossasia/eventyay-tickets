/* global ENV_DEVELOPMENT */
import cloneDeep from 'lodash/cloneDeep'
let config
if (ENV_DEVELOPMENT || !window.venueless) {
	const hostname = window.location.hostname
	config = {
		api: {
			socket: `ws://${hostname}:8375/ws/world/sample/`,
			upload: `http://${hostname}:8375/storage/upload/`,
			scheduleImport: `http://${hostname}:8375/storage/schedule_import/`,
			feedback: `http://${hostname}:8375/_feedback/`,
		},
		timetravelTo: '2020-08-26T06:49:28.975Z'
	}
} else {
	// load from index.html as `window.venueless = {…}`
	config = cloneDeep(window.venueless)
}
export default config

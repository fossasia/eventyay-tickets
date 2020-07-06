/* global ENV_DEVELOPMENT */
import cloneDeep from 'lodash/cloneDeep'
let config
if (ENV_DEVELOPMENT || !window.venueless) {
	config = {
		api: {
			socket: 'ws://localhost:8375/ws/world/sample/',
			upload: 'http://localhost:8375/storage/upload/',
		}
	}
} else {
	// load from index.html as `window.venueless = {…}`
	config = cloneDeep(window.venueless)
}
export default config

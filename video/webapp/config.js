import cloneDeep from 'lodash/cloneDeep'
let config
if (ENV_DEVELOPMENT || !window.venueless) {
	config = {
		api: {
			socket: 'ws://localhost:8000/ws/world/sample/'
		}
	}
} else {
	// load from index.html as `window.venueless = {…}`
	config = cloneDeep(window.venueless)
}
export default config

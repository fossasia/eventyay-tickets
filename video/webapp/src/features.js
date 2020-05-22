/* global ENV_DEVELOPMENT */

import config from 'config'

export default {
	enabled (feature) {
		return false
		if (ENV_DEVELOPMENT) return true
		return config.features.includes[feature]
	}
}

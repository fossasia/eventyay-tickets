/* global ENV_DEVELOPMENT */

import config from 'config'

export default {
	enabled(feature) {
		if (ENV_DEVELOPMENT) return true
		const feats = config.features
		if (Array.isArray(feats)) return feats.includes(feature)
		if (feats && typeof feats === 'object') return Boolean(feats[feature])
		return false
	}
}

import { Random, MersenneTwister19937 } from 'random-js'
import * as identiheart from './renderer-identiheart.js'
import * as initials from './renderer-initials.js'

const renderers = {
	identiheart,
	initials
}

const hashFunc = function (source) {
	return String(source).split('').reduce(function (a, b) {
		a = ((a << 5) - a) + b.charCodeAt(0)
		return a & a
	}, 0)
}

export function renderSvg (user, style) {
	const random = new Random(
		MersenneTwister19937.seed(hashFunc(user.profile?.avatar?.identicon ?? user.profile?.identicon ?? user.id))
	)

	const renderer = renderers[style] || identiheart

	const config = {
		colorPalette: renderer.definition.colorPalette.defaults
	}

	return renderer.renderSvg(random, user.profile, config)
}

export function renderUrl (user, style) {
	return `data:image/svg+xml;base64,${btoa(renderSvg(user, style).replace(/[\t\n]/g, ''))}`
}

export { renderers }

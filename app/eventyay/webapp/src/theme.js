// TODO
// - icon button hover background on dark bg
import Color from 'color'
import kebabCase from 'lodash/kebabCase'
import config from 'config'

import { normal as normalBlend } from 'color-blend'

const blend = function(background, foreground) {
	const { r, g, b, a } = normalBlend({
		r: background.red(),
		g: background.green(),
		b: background.blue(),
		a: background.alpha()
	}, {
		r: foreground.red(),
		g: foreground.green(),
		b: foreground.blue(),
		a: foreground.alpha()
	})
	return Color({ r, g, b, alpha: a })
}

// returns first color with enough (>=4.5) contrast or failing that, the color with the highest contrast
// on background, alpha gets blended
const firstReadable = function(colors, background = '#FFF', threshold = 4.5) {
	background = Color(background)
	let best
	let bestContrast = 0
	for (let color of colors) {
		color = Color(color)
		const contrast = background.contrast(blend(background, color))
		if (contrast >= threshold) return color
		else if (contrast > bestContrast) {
			best = color
			bestContrast = contrast
		}
	}
	// console.warn('THEME COLOR HAS NOT ENOUGH CONTRAST', best.string(), 'on', background.string(), '=', bestContrast)
	return best
}

const CLR_PRIMARY_TEXT = {LIGHT: Color('rgba(33, 133, 208, 1)'), DARK: Color('rgba(255, 255, 255, 1)')}
const CLR_SECONDARY_TEXT = {LIGHT: Color('rgba(0, 0, 0, .54)'), DARK: Color('rgba(255, 255, 255, .7)')}
const CLR_SECONDARY_TEXT_FALLBACK = {LIGHT: Color('rgba(0, 0, 0, .74)'), DARK: Color('rgba(255, 255, 255, .9)')}
const CLR_DISABLED_TEXT = {LIGHT: Color('rgba(0, 0, 0, .38)'), DARK: Color('rgba(255, 255, 255, .5)')}
const CLR_DIVIDERS = {LIGHT: Color('rgba(255, 255, 255, .63)'), DARK: Color('rgba(255, 255, 255, .63)')}

const DEFAULT_COLORS = {
	primary: '#2185d0',
	sidebar: '#2185d0',
	bbb_background: '#ffffff',
}

const DEFAULT_LOGO = {
	url: '/video/eventyay-video-logo.png',
	fitToWidth: false
}

const DEFAULT_IDENTICONS = {
	style: 'identiheart'
}

const configColors = config.theme?.colors || DEFAULT_COLORS

const themeConfig = {
	colors: configColors,
	logo: Object.assign({}, DEFAULT_LOGO, config.theme?.logo),
	streamOfflineImage: config.theme?.streamOfflineImage,
	identicons: Object.assign({}, DEFAULT_IDENTICONS, config.theme?.identicons),
}

const colors = Object.keys(DEFAULT_COLORS).reduce((acc, key) => (acc[key] = Color((configColors ?? DEFAULT_COLORS)[key]), acc), {})

// modded colors
colors.primaryDarken15 = colors.primary.darken(0.15)
colors.primaryDarken20 = colors.primary.darken(0.20)
colors.primaryAlpha60 = colors.primary.alpha(0.6)
colors.primaryAlpha50 = colors.primary.alpha(0.5)
colors.primaryAlpha18 = colors.primary.alpha(0.18)
// TODO hack alpha via rgba(var(--three-numbers), .X)

// text on main background
// TODO support switching main background
colors.textPrimary = firstReadable([CLR_PRIMARY_TEXT.LIGHT, CLR_PRIMARY_TEXT.DARK])
colors.textSecondary = firstReadable([CLR_SECONDARY_TEXT.LIGHT, CLR_SECONDARY_TEXT.DARK])
colors.textDisabled = firstReadable([CLR_DISABLED_TEXT.LIGHT, CLR_DISABLED_TEXT.DARK])
colors.dividers = firstReadable([CLR_DIVIDERS.LIGHT, CLR_DIVIDERS.DARK])

// button + inputs
colors.inputPrimaryBg = colors.primary
colors.inputPrimaryFg = firstReadable([CLR_PRIMARY_TEXT.LIGHT, CLR_PRIMARY_TEXT.DARK], colors.primary)
colors.inputPrimaryBgDarken = colors.primary.darken(0.15)
// secondary inputs are transparent
colors.inputSecondaryFg = colors.primary
colors.inputSecondaryFgAlpha = colors.primary.alpha(0.08)
// sidebar
colors.sidebarTextPrimary = firstReadable([CLR_PRIMARY_TEXT.LIGHT, CLR_PRIMARY_TEXT.DARK], colors.sidebar)
colors.sidebarTextSecondary = firstReadable([CLR_SECONDARY_TEXT.LIGHT, CLR_SECONDARY_TEXT_FALLBACK.LIGHT, CLR_SECONDARY_TEXT.DARK, CLR_SECONDARY_TEXT_FALLBACK.DARK], colors.sidebar)
colors.sidebarTextDisabled = firstReadable([CLR_DISABLED_TEXT.LIGHT, CLR_DISABLED_TEXT.DARK], colors.sidebar)
colors.sidebarActiveBg = firstReadable(['rgba(0, 0, 0, 0.08)', 'rgba(255, 255, 255, 0.4)'], colors.sidebar)
colors.sidebarActiveFg = firstReadable([CLR_PRIMARY_TEXT.LIGHT, CLR_PRIMARY_TEXT.DARK], colors.sidebar)
colors.sidebarHoverBg = firstReadable(['rgba(0, 0, 0, 0.12)', 'rgba(255, 255, 255, 0.3)'], colors.sidebar)
colors.sidebarHoverFg = firstReadable([CLR_PRIMARY_TEXT.LIGHT, CLR_PRIMARY_TEXT.DARK], colors.sidebar)

// TODO warn if contrast if failing

const themeVariables = {}
for (const [key, value] of Object.entries(colors)) {
	themeVariables[`--clr-${kebabCase(key)}`] = value.string()
}

export default themeConfig
export { themeVariables, colors, DEFAULT_COLORS, DEFAULT_LOGO, DEFAULT_IDENTICONS }

export function computeForegroundColor(bgColor) {
	return firstReadable([CLR_PRIMARY_TEXT.LIGHT, CLR_PRIMARY_TEXT.DARK], bgColor)
}

export function computeForegroundSidebarColor(colors) {
	const configColors = {
		primary: colors.primary,
		sidebar: colors.sidebar,
		bbb_background: colors.bbb_background,
	}
	const sbColors = Object.keys(DEFAULT_COLORS).reduce((acc, key) => {
		acc[key] = Color((configColors ?? DEFAULT_COLORS)[key])
		return acc
	}, {})
	sbColors.primaryDarken15 = sbColors.primary.darken(0.15)
	sbColors.primaryDarken20 = sbColors.primary.darken(0.20)
	sbColors.primaryAlpha60 = sbColors.primary.alpha(0.6)
	sbColors.primaryAlpha50 = sbColors.primary.alpha(0.5)
	sbColors.primaryAlpha18 = sbColors.primary.alpha(0.18)
	sbColors.inputPrimaryBg = sbColors.primary
	sbColors.inputPrimaryFg = firstReadable([CLR_PRIMARY_TEXT.LIGHT, CLR_PRIMARY_TEXT.DARK], sbColors.primary)
	sbColors.inputPrimaryBgDarken = sbColors.primary.darken(0.15)
	sbColors.inputSecondaryFg = sbColors.primary
	sbColors.inputSecondaryFgAlpha = sbColors.primary.alpha(0.08)
	sbColors.sidebarTextPrimary = firstReadable([CLR_PRIMARY_TEXT.LIGHT, CLR_PRIMARY_TEXT.DARK], sbColors.sidebar)
	sbColors.sidebarTextSecondary = firstReadable([CLR_SECONDARY_TEXT.LIGHT, CLR_SECONDARY_TEXT_FALLBACK.LIGHT, CLR_SECONDARY_TEXT.DARK, CLR_SECONDARY_TEXT_FALLBACK.DARK], sbColors.sidebar)
	sbColors.sidebarTextDisabled = firstReadable([CLR_DISABLED_TEXT.LIGHT, CLR_DISABLED_TEXT.DARK], sbColors.sidebar)
	sbColors.sidebarActiveBg = firstReadable(['rgba(0, 0, 0, 0.08)', 'rgba(255, 255, 255, 0.4)'], sbColors.sidebar)
	sbColors.sidebarActiveFg = firstReadable([CLR_PRIMARY_TEXT.LIGHT, CLR_PRIMARY_TEXT.DARK], sbColors.sidebar)
	sbColors.sidebarHoverBg = firstReadable(['rgba(0, 0, 0, 0.12)', 'rgba(255, 255, 255, 0.3)'], sbColors.sidebar)
	sbColors.sidebarHoverFg = firstReadable([CLR_PRIMARY_TEXT.LIGHT, CLR_PRIMARY_TEXT.DARK], sbColors.sidebar)

	for (const [key, value] of Object.entries(sbColors)) {
		themeVariables[`--clr-${kebabCase(key)}`] = value.string()
	}
}

export async function getThemeConfig() {
	// Fast path: if backend provided theme in injected config, just use it and avoid network 404 spam
	if (config.theme && (config.theme.colors || config.theme.logo)) {
		return {
			colors: config.theme.colors || configColors,
			logo: Object.assign({}, DEFAULT_LOGO, config.theme.logo),
			streamOfflineImage: config.theme.streamOfflineImage,
			identicons: Object.assign({}, DEFAULT_IDENTICONS, config.theme.identicons),
		}
	}
	if (config.noThemeEndpoint) {
		return {
			colors: configColors,
			logo: Object.assign({}, DEFAULT_LOGO, config.theme?.logo),
			streamOfflineImage: config.theme?.streamOfflineImage,
			identicons: Object.assign({}, DEFAULT_IDENTICONS, config.theme?.identicons),
		}
	}
	if (!config.api?.base) {
		return {
			colors: configColors,
			logo: Object.assign({}, DEFAULT_LOGO, config.theme?.logo),
			streamOfflineImage: config.theme?.streamOfflineImage,
			identicons: Object.assign({}, DEFAULT_IDENTICONS, config.theme?.identicons),
		}
	}
	const themeUrl = config.api.base + 'theme'
	try {
		const response = await fetch(themeUrl, {
			method: 'GET',
			headers: { 'Content-Type': 'application/json' }
		})
		if (response.ok) {
			const data = await response.json()
			return {
				colors: data.colors || configColors,
				logo: Object.assign({}, DEFAULT_LOGO, data.logo),
				streamOfflineImage: data.streamOfflineImage,
				identicons: Object.assign({}, DEFAULT_IDENTICONS, data.identicons),
			}
		} else {
			if (response.status !== 404) console.warn('Theme fetch failed', response.status, response.statusText)
			else console.info('Theme endpoint missing (404), using defaults')
		}
	} catch (e) {
		console.warn('Theme fetch error, using defaults', e)
	}
	return {
		colors: configColors,
		logo: Object.assign({}, DEFAULT_LOGO, config.theme?.logo),
		streamOfflineImage: config.theme?.streamOfflineImage,
		identicons: Object.assign({}, DEFAULT_IDENTICONS, config.theme?.identicons),
	}
}

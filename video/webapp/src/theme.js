// TODO
// - icon button hover background on dark bg
import Color from 'color'
import kebabCase from 'lodash/kebabCase'
import config from 'config'

import { normal as normalBlend } from 'color-blend'

const blend = function (background, foreground) {
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
const firstReadable = function (colors, background = '#FFF', threshold = 4.5) {
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

const CLR_PRIMARY_TEXT = {LIGHT: Color('rgba(0, 0, 0, .87)'), DARK: Color('rgba(255, 255, 255, 1)')}
const CLR_SECONDARY_TEXT = {LIGHT: Color('rgba(0, 0, 0, .54)'), DARK: Color('rgba(255, 255, 255, .7)')}
const CLR_SECONDARY_TEXT_FALLBACK = {LIGHT: Color('rgba(0, 0, 0, .74)'), DARK: Color('rgba(255, 255, 255, .9)')}
const CLR_DISABLED_TEXT = {LIGHT: Color('rgba(0, 0, 0, .38)'), DARK: Color('rgba(255, 255, 255, .5)')}
const CLR_DIVIDERS = {LIGHT: Color('rgba(255, 255, 255, .63)'), DARK: Color('rgba(255, 255, 255, .63)')}

const DEFAULT_COLORS = {
	primary: '#673ab7',
	sidebar: '#f9f9f9',//'#180044',
	bbb_background: '#333333',
}

const DEFAULT_LOGO = {
	url: '/venueless-logo-full-white.svg',
	fitToWidth: false
}

const configColors = config.theme?.colors

const themeConfig = {
	colors: configColors,
	logo: Object.assign(DEFAULT_LOGO, config.theme?.logo),
	streamOfflineImage: config.theme?.streamOfflineImage
}

const colors = Object.keys(DEFAULT_COLORS).reduce((acc, key) => (acc[key] = Color((configColors ?? DEFAULT_COLORS)[key]), acc), {}) // eslint-disable-line no-sequences

// modded colors
colors.primaryDarken15 = colors.primary.darken(0.15)
colors.primaryDarken20 = colors.primary.darken(0.20)
colors.primaryAlpha60 = colors.primary.alpha(0.6)
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
export { themeVariables, DEFAULT_COLORS, DEFAULT_LOGO }

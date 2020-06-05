import color from 'tinycolor2'
import kebabCase from 'lodash/kebabCase'
import config from 'config'

const CLR_PRIMARY_TEXT = {LIGHT: color('rgba(0, 0, 0, .87)'), DARK: color('rgba(255, 255, 255, 1)')}
const CLR_SECONDARY_TEXT = {LIGHT: color('rgba(0, 0, 0, .54)'), DARK: color('rgba(255, 255, 255, .7)')}
const CLR_DISABLED_TEXT = {LIGHT: color('rgba(0, 0, 0, .38)'), DARK: color('rgba(255, 255, 255, .5)')}
const CLR_DIVIDERS = {LIGHT: color('rgba(255, 255, 255, .63)'), DARK: color('rgba(255, 255, 255, .63)')}

const DEFAULT_COLORS = {
	primary: '#673ab7',
	sidebar: '#180044'
}

const DEFAULT_LOGO = {
	url: '/venueless-logo-full-white.svg',
	fitToWidth: false
}

const configColors = config.theme?.colors

const themeConfig = {
	colors: configColors,
	logo: Object.assign(DEFAULT_LOGO, config.theme?.logo)
}

const colors = Object.keys(DEFAULT_COLORS).reduce((acc, key) => (acc[key] = color((configColors ?? DEFAULT_COLORS)[key]), acc), {}) // eslint-disable-line no-sequences

// modded colors
colors.primaryDarken15 = colors.primary.clone().darken(15)
colors.primaryDarken20 = colors.primary.clone().darken(20)
colors.primaryAlpha60 = colors.primary.clone().setAlpha(0.6)
// text on main background
// TODO support switching main background
colors.textPrimary = color.mostReadable('#fff', [CLR_PRIMARY_TEXT.LIGHT, CLR_PRIMARY_TEXT.DARK])
colors.textSecondary = color.mostReadable('#fff', [CLR_SECONDARY_TEXT.LIGHT, CLR_SECONDARY_TEXT.DARK])
colors.textDisabled = color.mostReadable('#fff', [CLR_DISABLED_TEXT.LIGHT, CLR_DISABLED_TEXT.DARK])
colors.dividers = color.mostReadable('#fff', [CLR_DIVIDERS.LIGHT, CLR_DIVIDERS.DARK])

// button + inputs
colors.inputPrimaryBg = colors.primary
colors.inputPrimaryFg = color.mostReadable(colors.primary, [CLR_PRIMARY_TEXT.LIGHT, CLR_PRIMARY_TEXT.DARK])
colors.inputPrimaryBgDarken = colors.primary.clone().darken(15)
// secondary inputs are transparent
colors.inputSecondaryFg = colors.primary
colors.inputSecondaryFgAlpha = colors.primary.clone().setAlpha(0.08)
// sidebar
colors.sidebarTextPrimary = color.mostReadable(colors.sidebar, [CLR_PRIMARY_TEXT.LIGHT, CLR_PRIMARY_TEXT.DARK])
colors.sidebarTextSecondary = color.mostReadable(colors.sidebar, [CLR_SECONDARY_TEXT.LIGHT, CLR_SECONDARY_TEXT.DARK])
colors.sidebarTextDisabled = color.mostReadable(colors.sidebar, [CLR_DISABLED_TEXT.LIGHT, CLR_DISABLED_TEXT.DARK])
colors.sidebarActiveBg = color.mostReadable(colors.sidebar, ['rgba(0, 0, 0, 0.4)', 'rgba(255, 255, 255, 0.4)'])
colors.sidebarActiveFg = color.mostReadable(colors.sidebar, [CLR_PRIMARY_TEXT.LIGHT, CLR_PRIMARY_TEXT.DARK])
colors.sidebarHoverBg = color.mostReadable(colors.sidebar, ['rgba(0, 0, 0, 0.3)', 'rgba(255, 255, 255, 0.3)'])
colors.sidebarHoverFg = color.mostReadable(colors.sidebar, [CLR_PRIMARY_TEXT.LIGHT, CLR_PRIMARY_TEXT.DARK])

// TODO warn if contrast if failing

const themeVariables = {}
for (const [key, value] of Object.entries(colors)) {
	themeVariables[`--clr-${kebabCase(key)}`] = color(value).toRgbString()
}

export default themeConfig
export { themeVariables }

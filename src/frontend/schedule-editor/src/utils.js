// import i18n from 'i18n'

export function getLocalizedString (string) {
	if (typeof string === 'string') return string
	try {
		return Object.values(string)[0]
	} catch (e) {
		return ""
	}
	// return string[i18n.locale] || string[i18n.fallbackLocale] || Object.values(string)[0]
}

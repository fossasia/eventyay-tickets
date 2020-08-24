import i18n from 'i18n'

console.log(i18n)
export function getLocalizedString (string) {
	if (typeof string === 'string') return string
	return string[i18n.locale] || string[i18n.fallbackLocale] || Object.values(string)[0]
}

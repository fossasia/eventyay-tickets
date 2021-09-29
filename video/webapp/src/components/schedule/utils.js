import i18n from 'i18n'

export function getLocalizedString (string) {
	if (typeof string === 'string') return string
	for (const lang of i18n.languages) {
		if (string[lang]) return string[lang]
	}
	return Object.values(string)[0]
}

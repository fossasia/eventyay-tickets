import Vue from 'vue'
import VueI18n from 'vue-i18n'
import config from 'config'

Vue.use(VueI18n)

function loadLocaleMessages () {
	const locales = require.context('./locales', true, /[A-Za-z0-9-_,\s]+\.js$/i)
	const messages = {}
	locales.keys().forEach(key => {
		const matched = key.match(/([A-Za-z0-9-_]+)\./i)
		if (matched && matched.length > 1) {
			const locale = matched[1]
			messages[locale] = Object.assign({}, locales(key).default, config.theme?.textOverwrites ?? {})
		}
	})
	return messages
}

export default new VueI18n({
	locale: config.locale || 'en',
	fallbackLocale: 'en',
	messages: loadLocaleMessages()
})

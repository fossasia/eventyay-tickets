/* global ENV_DEVELOPMENT */
import i18next from 'i18next'
import config from 'config'
// Vue.use(VueI18n)
//
// function loadLocaleMessages () {
// 	const locales = require.context('./locales', true, /[A-Za-z0-9-_,\s]+\.js$/i)
// 	const messages = {}
// 	locales.keys().forEach(key => {
// 		const matched = key.match(/([A-Za-z0-9-_]+)\./i)
// 		if (matched && matched.length > 1) {
// 			const locale = matched[1]
// 			messages[locale] = Object.assign({}, locales(key).default, config.theme?.textOverwrites ?? {})
// 		}
// 	})
// 	return messages
// }
//
// export default new VueI18n({
// 	locale: config.locale || 'en',
// 	fallbackLocale: 'en',
// 	messages: loadLocaleMessages()
// })

export default async function (Vue) {
	await i18next
		// dynamic locale loader using webpack chunks
		.use({
			type: 'backend',
			init (services, backendOptions, i18nextOptions) {},
			async read (language, namespace, callback) {
				try {
					const locale = await import(/* webpackChunkName: "locale-[request]" */ `./locales/${language}.json`)
					callback(null, locale.default)
				} catch (error) {
					callback(error)
				}
			}
		})
		// inject custom theme text overwrites
		.use({
			type: 'postProcessor',
			name: 'themeOverwrites',
			process (value, key, options, translator) {
				return config.theme?.textOverwrites[key[0]] ?? value
			}
		})
		.init({
			lng: localStorage.userLanguage || config.defaultLocale || config.locale || 'en',
			fallbackLng: 'en',
			debug: ENV_DEVELOPMENT,
			keySeparator: false,
			nsSeparator: false,
			postProcess: ['themeOverwrites']
		})
	Vue.prototype.$i18n = i18next
	Vue.prototype.$t = i18next.t.bind(i18next)
}

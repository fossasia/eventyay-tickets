// Loads the translation file with `locale` from the head of files in /src/pretalx/locale/*
// and exposes the i18next api into global vue.
// Usable with `this.$t` or just `{{ $t('plz translate me') }}` in templates
//
// Also loads the moment locale for the given locale, if available.

import i18next from 'i18next'
import moment from 'moment-timezone'

const localeModules = import.meta.glob('../../../locale/*/LC_MESSAGES/django.po')
const momentLocaleModules = import.meta.glob('../../node_modules/moment/dist/locale/*.js')

export default async function (locale) {
  const localeModule = await localeModules[`../../../locale/${locale}/LC_MESSAGES/django.po`]?.()
	const momentLocale = locale.split("_")[0]
	const momentLocaleModule = await momentLocaleModules[`../../node_modules/moment/dist/locale/${momentLocale}.js`]?.()
	moment.locale(momentLocale)

  return {
    install (app) {
      i18next.init({
        lng: locale,
				returnEmptyString: false,
        debug: false,
				nsSeparator: false,
				keySeparator: false,
        resources: {
          [locale]: {
            translation: localeModule?.default
          }
        },
        interpolation: {
          // gettext style interpolation
          prefix: '%(',
          suffix: ')'
        }
      })
      app.config.globalProperties.$i18n = i18next
      app.config.globalProperties.$t = i18next.t.bind(i18next)
    }
  }
}

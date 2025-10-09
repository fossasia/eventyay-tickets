// Loads the translation file with `locale` from the head of files in /src/pretalx/locale/*
// and exposes the i18next api into global vue.
// Usable with `this.$t` or just `{{ $t('plz translate me') }}` in templates
//
// Also loads the moment locale for the given locale, if available.

import i18next from 'i18next'
import moment from 'moment-timezone'

// Define the module type for our translation files
interface TranslationModule {
  default: Record<string, string>;
}

const localeModules = import.meta.glob<TranslationModule>('../../../../locale/*/LC_MESSAGES/django.po')
const momentLocaleModules = import.meta.glob('../../node_modules/moment/dist/locale/*.js')

export default async function (locale: string) {
    const moduleLoader = localeModules[`../../../../locale/${locale}/LC_MESSAGES/django.po`]
    const localeModule = moduleLoader ? (await moduleLoader())?.default : {}
    const momentLocale = locale.split("_")[0]
    await momentLocaleModules[`../../node_modules/moment/dist/locale/${momentLocale}.js`]?.()
    moment.locale(momentLocale)

    return {
        install(app: any) {
            i18next.init({
                lng: locale,
                returnEmptyString: false,
                debug: false,
                nsSeparator: false,
                keySeparator: false,
                resources: {
                    [locale]: {
                        translation: localeModule || {}
                    }
                },
                interpolation: {
                    prefix: '%(',
                    suffix: ')'
                }
            })
            app.config.globalProperties.$i18n = i18next
            app.config.globalProperties.$t = i18next.t.bind(i18next)
        }
    }
}

// Loads the translation file with `locale` from the head of files in /src/pretalx/locale/*
// and exposes the i18next api into global vue.
// Usable with `this.$t` or just `{{ $t('plz translate me') }}` in templates

import i18next from 'i18next'
const localeModules = import.meta.glob('../../../../pretalx/locale/*/LC_MESSAGES/django.po')

export default async function (locale) {
  const localeModule = await localeModules[`../../../../pretalx/locale/${locale}/LC_MESSAGES/django.po`]()
  return {
    install (app) {
      i18next.init({
        lng: locale,
        debug: true,
        resources: {
          [locale]: {
            translation: localeModule.default
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

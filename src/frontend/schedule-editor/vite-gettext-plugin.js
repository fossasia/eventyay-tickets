import { gettextToI18next } from 'i18next-conv'
const fileRegex = /locale\/(.*)\/LC_MESSAGES\/.*\.po$/

export default function loadGettext () {
  return {
    name: 'load-gettext',
    async transform (src, id) {
      if (fileRegex.test(id)) {
		const lang = id.match(fileRegex)[1]
        return {
          code: 'export default ' + await gettextToI18next(lang, src), // TODO first param should be locale
          map: { mappings: '' } // provide source map if available
        }
      }
    }
  }
}

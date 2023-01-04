import { gettextToI18next } from 'i18next-conv'
const fileRegex = /\.po$/

export default function loadGettext () {
  return {
    name: 'load-gettext',
    async transform (src, id) {
      if (fileRegex.test(id)) {
        return {
          code: 'export default ' + await gettextToI18next('', src), // TODO first param should be locale
          map: { mappings: '' } // provide source map if available
        }
      }
    }
  }
}

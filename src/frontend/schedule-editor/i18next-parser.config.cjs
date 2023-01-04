const VueLexer = require('./i18next-parser-vue-lexer.cjs')

module.exports = {
  locales: ['en'],
  lexers: {
    vue: [VueLexer]
  }
}

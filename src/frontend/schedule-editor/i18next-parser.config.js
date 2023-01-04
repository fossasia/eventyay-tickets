const VueLexer = require('./i18next-parser-vue-lexer.js')

module.exports = {
  locales: ['en'],
  lexers: {
    vue: [VueLexer]
  }
}

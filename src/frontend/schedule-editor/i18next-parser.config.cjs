const VueLexer = require('./i18next-parser-vue-lexer.cjs')

// Used via the pretalx makemessages command

module.exports = {
  locales: ['en'],
  lexers: {
    vue: [VueLexer]
  }
}

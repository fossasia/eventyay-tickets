// Used via the pretalx makemessages command

module.exports = {
  createOldCatalogs: false,
  verbose: true,
  locales: ['en'],
  lexers: {
    vue: [
        {lexer: 'JavascriptLexer', functions: ['$t', 't']},
    ]
  }
}

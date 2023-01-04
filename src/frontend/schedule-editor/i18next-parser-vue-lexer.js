const BaseLexer = require('i18next-parser/dist/lexers/base-lexer').default
const JavascriptLexer = require('i18next-parser/dist/lexers/javascript-lexer.js').default
const { compileTemplate } = require('@vue/compiler-sfc')

module.exports = class VueLexer extends BaseLexer {
  constructor (options = {}) {
    super(options)

    this.functions = options.functions || ['$t']
  }

  extract (content, filename) {
    let keys = []

    const Lexer = new JavascriptLexer()
    Lexer.on('warning', (warning) => this.emit('warning', warning))
    keys = keys.concat(Lexer.extract(content))

    const compiledTemplate = compileTemplate({
      source: content
    }).code
    const Lexer2 = new JavascriptLexer({ functions: this.functions })
    Lexer2.on('warning', (warning) => this.emit('warning', warning))
    keys = keys.concat(Lexer2.extract(compiledTemplate))

    return keys
  }
}

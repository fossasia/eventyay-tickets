import Quill from 'quill'
import BaseTheme, { BaseTooltip } from 'quill/themes/base'
import Emitter from 'quill/core/emitter'
import { Range } from 'quill/core/selection'
import { defaultsDeep } from 'lodash'

const LinkBlot = Quill.import('formats/link')

// This is based on the "snow" theme from quill, but optimized to work with buntpapier
class BuntTheme extends BaseTheme {
	extendToolbar (toolbar) {
		this.tooltip = new BuntTooltip(this.quill, this.options.bounds)
		if (toolbar.container.querySelector('.ql-link')) {
			this.quill.keyboard.addBinding({ key: 'K', shortKey: true }, function (range, context) {
				toolbar.handlers.link.call(toolbar, !context.format.link)
			})
		}
	}
}
BuntTheme.DEFAULTS = defaultsDeep(defaultsDeep({}, BaseTheme.DEFAULTS), {
	modules: {
		toolbar: {
			handlers: {
				link: function (value) {
					if (value) {
						const range = this.quill.getSelection()
						if (range == null || range.length === 0) return
						let preview = this.quill.getText(range)
						if (/^\S+@\S+\.\S+$/.test(preview) && preview.indexOf('mailto:') !== 0) {
							preview = 'mailto:' + preview
						}
						const tooltip = this.quill.theme.tooltip
						tooltip.edit('link', preview)
					} else {
						this.quill.format('link', false)
					}
				}
			}
		}
	}
})

class BuntTooltip extends BaseTooltip {
	constructor (quill, bounds) {
		super(quill, bounds)
		this.preview = this.root.querySelector('a.ql-preview')
	}

	listen () {
		super.listen()
		this.root.querySelector('a.ql-action').addEventListener('click', (event) => {
			if (this.root.classList.contains('ql-editing')) {
				this.save()
			} else {
				this.edit('link', this.preview.textContent)
			}
			event.preventDefault()
		})
		this.root.querySelector('a.ql-remove').addEventListener('click', (event) => {
			if (this.linkRange != null) {
				const range = this.linkRange
				this.restoreFocus()
				this.quill.formatText(range, 'link', false, Emitter.sources.USER)
				delete this.linkRange
			}
			event.preventDefault()
			this.hide()
		})
		this.quill.on(Emitter.events.SELECTION_CHANGE, (range, oldRange, source) => {
			if (range == null) return
			if (range.length === 0 && source === Emitter.sources.USER) {
				const [link, offset] = this.quill.scroll.descendant(LinkBlot, range.index)
				console.log('link', LinkBlot, link, this.quill.scroll.descendant(LinkBlot, range.index))
				if (link != null) {
					this.linkRange = new Range(range.index - offset, link.length())
					const preview = LinkBlot.formats(link.domNode)
					this.preview.textContent = preview
					this.preview.setAttribute('href', preview)
					this.show()
					this.position(this.quill.getBounds(this.linkRange))
					return
				}
			} else {
				delete this.linkRange
			}
			this.hide()
		})
	}

	show () {
		super.show()
		this.root.removeAttribute('data-mode')
	}
}
BuntTooltip.TEMPLATE = [
	'<a class="ql-preview" rel="noopener noreferrer" target="_blank" href="about:blank"></a>',
	'<input type="text" data-formula="e=mc^2" data-link="https://venueless.org" data-video="Embed URL">',
	'<a class="ql-action"></a>',
	'<a class="ql-remove"></a>'
].join('')

export default BuntTheme

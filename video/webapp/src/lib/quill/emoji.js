import Quill from 'quill'
import { nativeToStyle as nativeEmojiToStyle, objectToCssString } from 'lib/emoji'

const Embed = Quill.import('blots/embed')

class EmojiBlot extends Embed {
	static create(value) {
		const node = super.create()
		node.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
		node.style.cssText = objectToCssString(nativeEmojiToStyle(value))
		node.dataset.emoji = value
		return node
	}

	static value(node) {
		return node.dataset.emoji
	}
}

EmojiBlot.blotName = 'emoji'
EmojiBlot.className = 'emoji'
EmojiBlot.tagName = 'img'

Quill.register(EmojiBlot)

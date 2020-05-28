<template lang="pug">
bunt-input-outline-container.c-chat-input
	.contenteditable(ref="contenteditable", contenteditable="true", @keydown.enter="send", @paste.prevent.stop="onPaste")
	.btn-emoji-picker(@click="toggleEmojiPicker")
		svg(xmlns="http://www.w3.org/2000/svg", viewBox="0 0 24 24")
			path(d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0m0 22C6.486 22 2 17.514 2 12S6.486 2 12 2s10 4.486 10 10-4.486 10-10 10")
			path(d="M8 7a2 2 0 1 0-.001 3.999A2 2 0 0 0 8 7M16 7a2 2 0 1 0-.001 3.999A2 2 0 0 0 16 7M15.232 15c-.693 1.195-1.87 2-3.349 2-1.477 0-2.655-.805-3.347-2H15m3-2H6a6 6 0 1 0 12 0")
	.emoji-picker-blocker(v-if="showEmojiPicker", @click="showEmojiPicker = false")
	emoji-picker(v-if="showEmojiPicker", @selected="addEmoji")
	bunt-icon-button#btn-send(@click="send") send
</template>
<script>
// TODO
// - multiline
// - intercept copy
// - parse ascii emoticons ;)
// - parse colol emoji :+1:
// - close emoji picker
import EmojiPicker from 'components/EmojiPicker'
import { getEmojiPosition } from 'lib/emoji'
import { NimbleEmojiIndex } from 'emoji-mart'
import data from 'emoji-mart/data/twitter.json'

const emojiIndex = new NimbleEmojiIndex(data)

export default {
	components: { EmojiPicker },
	data () {
		return {
			showEmojiPicker: false
		}
	},
	computed: {},
	created () {},
	mounted () {
		document.addEventListener('selectionchange', this.onSelectionchange)
	},
	destroyed () {
		document.removeEventListener('selectionchange', this.onSelectionchange)
	},
	methods: {
		toggleEmojiPicker () {
			this.showEmojiPicker = !this.showEmojiPicker
		},
		onSelectionchange () {
			const selection = window.getSelection()
			const range = selection.getRangeAt(0)
			const insideEditable = (range.startContainer.closest ? range.startContainer : range.startContainer.parentElement).closest('.contenteditable')
			if (!insideEditable) return
			this.selectedRange = range
		},
		onPaste (event) {
			const text = event.clipboardData.getData('text/plain')
			document.execCommand('insertText', false, text) // HACK obsolete api
		},
		send () {
			event.preventDefault()
			let message = ''
			for (const node of this.$refs.contenteditable.childNodes) {
				if (node.nodeType === Node.TEXT_NODE) {
					message += node.textContent
				} else if (node.dataset?.emoji) {
					message += emojiIndex.emojis[node.dataset.emoji].native
				}
			}
			this.$emit('send', message)
			this.$refs.contenteditable.innerHTML = ''
		},
		addEmoji (emoji) {
			// TODO skin color
			this.showEmojiPicker = false
			const selection = window.getSelection()
			const position = getEmojiPosition(emoji)
			const emojiEl = document.createElement('img')
			emojiEl.classList.add('emoji')
			emojiEl.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
			emojiEl.style = `background-position: ${position};`
			emojiEl.dataset.emoji = emoji.id
			if (this.selectedRange) {
				this.selectedRange.insertNode(emojiEl)
			} else {
				this.$refs.contenteditable.appendChild(emojiEl)
			}
			const index = Array.from(this.$refs.contenteditable.childNodes).indexOf(emojiEl) + 1
			const range = document.createRange()
			range.setStart(this.$refs.contenteditable, index)
			range.setEnd(this.$refs.contenteditable, index)
			selection.removeAllRanges()
			selection.addRange(range)
		}
	}
}
</script>
<style lang="stylus">
.c-chat-input
	position: relative
	display: flex
	width: calc(100% - 27px) // width of emoji picker for sidebar mode
	height: 36px
	box-sizing: border-box
	&.bunt-input-outline-container
		padding: 8px 32px 8px 32px
	.contenteditable
		margin: 0
		outline: none
		font-size: 16px
		height: 20px
		white-space: nowrap
		overflow: scroll
		&::-webkit-scrollbar
			display: none
		-ms-overflow-style: none
		scrollbar-width: none
		.emoji
			margin: 0 2px
			vertical-align: bottom
			line-height: 20px
			width: 20px
			height: 20px
			display: inline-block
			background-image: url("~emoji-datasource-twitter/img/twitter/sheets-256/64.png")
			background-size: 5700% 5700%
	.bunt-input
		input-style(size: compact)
		padding: 0
		input
			padding-left: 32px
	.btn-emoji-picker
		height: 28px
		width: 28px
		box-sizing: border-box
		padding: 4px
		position: absolute
		left: 4px
		top: 4px
		&:hover
			border-radius: 50%
			background-color: $clr-grey-100
		svg
			path
				fill: $clr-secondary-text-light
	.emoji-picker-blocker
		position: fixed
		top: 0
		left: 0
		width: 100vw
		height: var(--vh100)
		z-index: 4999
	.c-emoji-picker
		position: absolute
		bottom: 36px
		left: 0
		z-index: 5000
	#btn-send
		position: absolute
		right: 4px
		top: 4px
		icon-button-style(color: $clr-secondary-text-light)
		height: 28px
		width: 28px
		.bunt-icon
			font-size: 18px
			height: 24px
			line-height: @height
</style>

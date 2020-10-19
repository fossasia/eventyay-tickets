<template lang="pug">
bunt-input-outline-container.c-chat-input
	.editor(ref="editor")
	.btn-emoji-picker(@click="toggleEmojiPicker")
		svg(xmlns="http://www.w3.org/2000/svg", viewBox="0 0 24 24")
			path(d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0m0 22C6.486 22 2 17.514 2 12S6.486 2 12 2s10 4.486 10 10-4.486 10-10 10")
			path(d="M8 7a2 2 0 1 0-.001 3.999A2 2 0 0 0 8 7M16 7a2 2 0 1 0-.001 3.999A2 2 0 0 0 16 7M15.232 15c-.693 1.195-1.87 2-3.349 2-1.477 0-2.655-.805-3.347-2H15m3-2H6a6 6 0 1 0 12 0")
	.emoji-picker-blocker(v-if="showEmojiPicker", @click="showEmojiPicker = false")
	emoji-picker(v-if="showEmojiPicker", @selected="addEmoji")
	upload-button#btn-file(@change="attachFiles", accept="image/png, image/jpg, application/pdf, .png, .jpg, .jpeg, .pdf", icon="paperclip", multiple=true)
	bunt-icon-button#btn-send(@click="send") send
	.files-preview(v-if="files.length > 0 || uploading")
		template(v-for="file in files")
			.chat-file(v-if="file === null")
				i.bunt-icon.mdi.mdi-alert-circle.upload-error
				bunt-icon-button#btn-remove-attachment(@click="files.pop(file)") close-circle
			template(v-else)
				.chat-image(v-if="file.mimeType.startsWith('image/')")
					img(:src="file.url")
					bunt-icon-button#btn-remove-attachment(@click="files.pop(file)") close-circle
				.chat-file(v-else)
					a.chat-file-content(:href="file.url" target="_blank")
						i.bunt-icon.mdi.mdi-file
						| {{ file.name }}
					bunt-icon-button#btn-remove-attachment(@click="files.pop(file)") close-circle
		bunt-progress-circular(size="small" v-if="uploading")
</template>
<script>
/* global ENV_DEVELOPMENT */
// TODO
// - parse ascii emoticons ;)
// - parse colol emoji :+1:
// - add scrollbar when overflowing parent
import api from 'lib/api'
import Quill from 'quill'
import 'quill/dist/quill.core.css'
import EmojiPicker from 'components/EmojiPicker'
import UploadButton from 'components/UploadButton'
import { getEmojiPosition, nativeToOps, toNative } from 'lib/emoji'

const Delta = Quill.import('delta')
const Embed = Quill.import('blots/embed')
class EmojiBlot extends Embed {
	static create (value) {
		const node = super.create()
		const position = getEmojiPosition(value)
		node.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
		node.style = `background-position: ${position};`
		node.dataset.emoji = value
		return node
	}

	static value (node) {
		return node.dataset.emoji
	}
}

EmojiBlot.blotName = 'emoji'
EmojiBlot.className = 'emoji'
EmojiBlot.tagName = 'img'

Quill.register(EmojiBlot)

export default {
	components: { EmojiPicker, UploadButton },
	props: {
		message: Object // initialize with existing message to edit
	},
	data () {
		return {
			showEmojiPicker: false,
			files: [],
			uploading: false
		}
	},
	computed: {},
	mounted () {
		this.quill = new Quill(this.$refs.editor, {
			debug: ENV_DEVELOPMENT ? 'info' : 'warn',
			placeholder: this.$t('ChatInput:input:placeholder'),
			formats: ['emoji'],
			modules: {
				keyboard: {
					bindings: {
						enter: {
							key: 'Enter',
							handler: this.send
						}
					}
				}
			}
		})
		if (this.message) {
			this.quill.setContents(nativeToOps(this.message.content?.body))
		}
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
		send () {
			const contents = this.quill.getContents()
			let text = ''
			for (const op of contents.ops) {
				if (typeof op.insert === 'string') {
					text += op.insert
				} else if (op.insert.emoji) {
					text += toNative(op.insert.emoji)
				}
			}
			text = text.trim()
			if (this.files.length > 0) {
				this.$emit('sendFiles', this.files.filter(it => it != null), text)
				this.files = []
			} else {
				this.$emit('send', text)
			}
			this.quill.setContents([{insert: '\n'}])
		},
		async attachFiles (event) {
			const files = Array.from(event.target.files)
			if (files.length === 0) return

			this.uploading = true
			const requests = files.map(f => {
				return api.uploadFilePromise(f, f.name)
			})
			var fileInfos = (await Promise.all(requests)).map((response, i) => {
				if (response.error) {
					return null
				} else {
					return {
						url: response.url,
						mimeType: files[i].type,
						name: files[i].name
					}
				}
			})
			Array.prototype.push.apply(this.files, fileInfos)
			this.uploading = false
		},
		addEmoji (emoji) {
			// TODO skin color
			this.showEmojiPicker = false
			const selection = this.quill.getSelection(true)
			this.quill.updateContents(new Delta().retain(selection.index).delete(selection.length).insert({emoji: emoji.id}), 'user')
			this.quill.setSelection(selection.index + 1, 0)
		}
	}
}
</script>
<style lang="stylus">
.c-chat-input
	position: relative
	display: flex
	width: calc(100% - 27px) // width of emoji picker for sidebar mode
	min-height: 36px
	box-sizing: border-box
	&.bunt-input-outline-container
		padding: 8px 60px 6px 36px
	.ql-editor
		font-size: 16px
		padding: 0
		font-family: $font-stack
		&.ql-blank::before
			font-style: normal
			color: var(--clr-text-secondary)
			line-height: 22px
			left: 0
		p
			font-size: 16px
			line-height: 22px
			overflow-wrap: break-word
		.emoji
			margin: 0 2px
			line-height: 22px
			width: 20px
			height: 20px
			vertical-align: middle
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
		z-index: 800
	.c-emoji-picker
		position: absolute
		bottom: 36px
		left: 0
		z-index: 801
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
	#btn-file
		position: absolute
		right: 32px
		top: 4px
		icon-button-style(color: $clr-secondary-text-light)
		height: 28px
		width: 28px
		.bunt-icon
			font-size: 18px
			height: 24px
			line-height: @height
	#btn-remove-attachment
		position: absolute
		right: -14px
		top: -14px
		icon-button-style(color: $clr-secondary-text-light)
		height: 28px
		width: 28px
		background: white
	.files-preview
		position: relative
		width: 100%
		box-sizing: border-box
		background white
		margin-top: 16px
		.chat-image
			position: relative
			display: inline-block
			width: 60px
			height: 60px
			box-sizing: border-box
			border-radius 2px
			border: 1px solid $clr-grey-400
			margin-right: 12px
			margin-bottom: 12px
			vertical-align: top
			img
				object-fit: cover
				width: 100%
				height: 100%
		.chat-file
			position: relative
			display: inline-block
			height: 60px
			min-width 60px
			max-width: 100px
			text-align: center
			border-radius 2px
			border: 1px solid $clr-grey-400
			padding: 12px 8px
			box-sizing: border-box
			margin-right: 12px
			margin-bottom: 12px
			vertical-align: top
			.upload-error
				color: $clr-danger
			.chat-file-content
				display: block
				text-overflow: ellipsis
				overflow: hidden
				white-space: nowrap
</style>

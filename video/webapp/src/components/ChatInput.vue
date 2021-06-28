<template lang="pug">
bunt-input-outline-container.c-chat-input
	.editor(ref="editor")
	emoji-picker-button(@selected="addEmoji")
	upload-button#btn-file(accept="image/png, image/jpg, application/pdf, .png, .jpg, .jpeg, .pdf", icon="paperclip", multiple=true, :tooltip="$t('ChatInput:btn-file:tooltip')", @change="attachFiles")
	bunt-icon-button#btn-send(:tooltip="$t('ChatInput:btn-send:tooltip')", tooltip-placement="top-end", @click="send") send
	.files-preview(v-if="files.length > 0 || uploading")
		template(v-for="file in files")
			.chat-file(v-if="file === null")
				i.bunt-icon.mdi.mdi-alert-circle.upload-error
				bunt-icon-button#btn-remove-attachment(@click="removeFile(file)") close-circle
			template(v-else)
				.chat-image(v-if="file.mimeType.startsWith('image/')")
					img(:src="file.url")
					bunt-icon-button#btn-remove-attachment(@click="removeFile(file)") close-circle
				.chat-file(v-else)
					a.chat-file-content(:href="file.url" target="_blank")
						i.bunt-icon.mdi.mdi-file
						| {{ file.name }}
					bunt-icon-button#btn-remove-attachment(@click="removeFile(file)") close-circle
		bunt-progress-circular(size="small" v-if="uploading")
</template>
<script>
/* global ENV_DEVELOPMENT */
// TODO
// - parse ascii emoticons ;)
// - parse colon emoji :+1:
// - add scrollbar when overflowing parent
import api from 'lib/api'
import Quill from 'quill'
import 'quill/dist/quill.core.css'
import EmojiPickerButton from 'components/EmojiPickerButton'
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
	components: { EmojiPickerButton, UploadButton },
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
			if (this.message.content?.files?.length > 0) {
				this.files = this.message.content.files
			}
		}
		document.addEventListener('selectionchange', this.onSelectionchange)
	},
	destroyed () {
		document.removeEventListener('selectionchange', this.onSelectionchange)
	},
	methods: {
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
				this.$emit('send', {
					type: 'files',
					files: this.files.filter(file => file),
					body: text
				})
				this.files = []
			} else {
				this.$emit('send', {
					type: 'text',
					body: text
				})
			}
			this.quill.setContents([{insert: '\n'}])
		},
		async attachFiles (event) {
			const files = Array.from(event.target.files)
			if (files.length === 0) return

			this.uploading = true
			// TODO upload files sequentially
			const requests = files.map(file => api.uploadFilePromise(file, file.name))
			const fileInfos = (await Promise.all(requests)).map((response, i) => {
				if (response.error) {
					// TODO actually handle and display error
					return null
				} else {
					return {
						url: response.url,
						mimeType: files[i].type,
						name: files[i].name
					}
				}
			})
			this.files.push(...fileInfos)
			this.uploading = false
		},
		addEmoji (emoji) {
			// TODO skin color
			const selection = this.quill.getSelection(true)
			this.quill.updateContents(new Delta().retain(selection.index).delete(selection.length).insert({emoji: emoji.id}), 'user')
			this.quill.setSelection(selection.index + 1, 0)
		},
		removeFile (file) {
			const index = this.files.indexOf(file)
			if (index > -1) {
				this.files.splice(index, 1)
			}
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
			image-rendering: -webkit-optimize-contrast
	.bunt-input
		input-style(size: compact)
		padding: 0
		input
			padding-left: 32px
	.c-emoji-picker-button .btn-emoji-picker
		position: absolute
		left: 4px
		top: 4px
		height: 28px
		width: @height
		padding: 4px
		svg
			path
				fill: $clr-secondary-text-light
	#btn-send, #btn-file .bunt-icon-button
		icon-button-style(color: $clr-secondary-text-light)
		height: 28px
		width: 28px
		.bunt-icon
			font-size: 18px
			height: 24px
			line-height: @height
	#btn-send
		position: absolute
		right: 4px
		top: 4px
	#btn-file
		position: absolute
		right: 32px
		top: 4px
	#btn-remove-attachment
		position: absolute
		right: -14px
		top: -14px
		icon-button-style(color: $clr-secondary-text-light)
		height: 28px
		width: 28px
		background: white
	.files-preview
		display: flex
		flex-wrap: wrap
		padding-top: 16px
		.chat-image, .chat-file
			position: relative
			height: 60px
			border-radius: 2px
			border: border-separator()
			margin: 0 12px 12px 0
		.chat-image
			width: 60px
			img
				object-fit: cover
				width: 100%
				height: 100%
		.chat-file
			min-width: 60px
			max-width: 100px
			text-align: center
			.upload-error
				color: $clr-danger
			.chat-file-content
				ellipsis()
				line-height: 60px
</style>

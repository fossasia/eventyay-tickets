<template lang="pug">
.c-chat-message(:class="[mode, {selected, readonly, 'system-message': isSystemMessage, 'merge-with-previous-message': mergeWithPreviousMessage, 'merge-with-next-message': mergeWithNextMessage}]")
	.avatar-column
		avatar(v-if="!mergeWithPreviousMessage", :user="sender", :size="avatarSize", @click.native="showAvatarCard", ref="avatar")
		.timestamp(v-if="mergeWithPreviousMessage") {{ shortTimestamp }}
	template(v-if="message.event_type === 'channel.message'")
		.content-wrapper
			.message-header(v-if="!mergeWithPreviousMessage")
				.display-name(@click="showAvatarCard")
					| {{ senderDisplayName }}
					.ui-badge(v-for="badge in sender.badges") {{ badge }}
				.timestamp {{ timestamp }}
			template(v-if="['text', 'files'].includes(message.content.type)")
				chat-input(v-if="editing", :message="message", @send="editMessage")
				.content(v-else-if="message.content.type === 'text'", v-html="content")
				.content(v-else)
					span(v-if="message.content.body", v-html="content")
					.files(v-for="file in message.content.files")
						a(v-if="file.mimeType.startsWith('image/')", :href="file.url", target="_blank")
							img.chat-image(:src="file.url")
						a.chat-file(v-else, :href="file.url", target="_blank")
							i.bunt-icon.mdi.mdi-file
							| {{ file.name }}
			.call(v-else-if="message.content.type === 'call'")
				.prompt(v-if="message.sender === user.id") You started a video call
				.prompt(v-else) {{ senderDisplayName }} invited you to a video call
				bunt-button(@click="$store.dispatch('chat/joinCall', message.content.body)") Join
			a.preview-card(v-if="message.content.preview_card", :href="message.content.preview_card.url", target="_blank")
				.url {{ message.content.preview_card.url }}
				img(v-if="message.content.preview_card.image", :src="message.content.preview_card.image")
				.title {{ message.content.preview_card.title }}
				.description {{ message.content.preview_card.description }}
			.reactions(v-if="Object.keys(message.reactions).length > 0")
				.reaction(v-for="users, emoji of message.reactions", :class="{'reacted-by-me': users.includes(user.id)}", @click="toggleReaction(emoji, users)", @pointerenter="initReactionTooltip($event, {emoji, users})", @pointerleave="reactionTooltip = null")
					span.emoji(:style="nativeEmojiToStyle(emoji)")
					.count {{ users.length }}
				emoji-picker-button(@selected="addReaction", strategy="fixed", placement="top-start", :offset="[0, 3]", icon-style="plus")
				.reaction-tooltip(v-if="reactionTooltip", ref="reactionTooltip")
					.arrow(data-popper-arrow="")
					.emoji-wrapper
						.emoji(:style="nativeEmojiToStyle(reactionTooltip.emoji)")
					.description
						span.users {{ reactionTooltip.usersString }}
						|  reacted with
						span.emoji-text  {{ getEmojiDataFromNative(reactionTooltip.emoji).short_names[0] }}
		.actions(v-if="!readonly")
			emoji-picker-button(@selected="addReaction", strategy="fixed", placement="bottom-end", :offset="[36, 3]", icon-style="plus")
			menu-dropdown(v-if="(hasPermission('room:chat.moderate') || message.sender === user.id)", v-model="selected", placement="bottom-end", :offset="[0, 3]")
				template(v-slot:button="{toggle}")
					bunt-icon-button(@click="toggle") dots-vertical
				template(v-slot:menu)
					.edit-message(v-if="message.sender === user.id && message.content.type !== 'call'", @click="startEditingMessage") {{ $t('ChatMessage:message-edit:label') }}
					.delete-message(@click="selected = false, showDeletePrompt = true") {{ $t('ChatMessage:message-delete:label') }}
	template(v-else-if="message.event_type === 'channel.member'")
		.system-content {{ sender.profile ? sender.profile.display_name : message.sender }} {{ message.content.membership === 'join' ? $t('ChatMessage:join-message:text') : $t('ChatMessage:leave-message:text') }}
	chat-user-card(v-if="showingAvatarCard", ref="avatarCard", :sender="sender", @close="showingAvatarCard = false")
	prompt.delete-message-prompt(v-if="showDeletePrompt", @close="showDeletePrompt = false")
		.prompt-content
			h2 Delete this message?
			.message-to-delete-wrapper
				chat-message(:message="message", mode="standalone", :readonly="true")
			.actions
				bunt-button#btn-cancel(@click="showDeletePrompt = false") cancel
				bunt-button#btn-delete-message(@click="deleteMessage") {{ $t('ChatMessage:message-delete:label') }}
</template>
<script>
// TODO
// - cancel editing
// - handle editing error
import moment from 'moment'
import MarkdownIt from 'markdown-it'
import { mapState, mapGetters } from 'vuex'
import { markdownEmoji, nativeToStyle as nativeEmojiToStyle, getEmojiDataFromNative } from 'lib/emoji'
import { createPopper } from '@popperjs/core'
import Avatar from 'components/Avatar'
import ChatInput from 'components/ChatInput'
import ChatUserCard from 'components/ChatUserCard'
import EmojiPickerButton from 'components/EmojiPickerButton'
import MenuDropdown from 'components/MenuDropdown'
import Prompt from 'components/Prompt'

const DATETIME_FORMAT = 'DD.MM. LT'
const TIME_FORMAT = 'LT'

const markdownIt = MarkdownIt('zero', {
	linkify: true // TODO more tlds
})
markdownIt.enable('linkify')
markdownIt.renderer.rules.link_open = function (tokens, idx, options, env, self) {
	tokens[idx].attrPush(['target', '_blank'])
	tokens[idx].attrPush(['rel', 'noopener noreferrer'])
	return self.renderToken(tokens, idx, options)
}

markdownIt.use(markdownEmoji)

const generateHTML = function (input) {
	if (!input) return
	return markdownIt.renderInline(input)
}

export default {
	name: 'ChatMessage',
	components: { Avatar, ChatInput, ChatUserCard, EmojiPickerButton, MenuDropdown, Prompt },
	props: {
		message: Object,
		previousMessage: Object,
		nextMessage: Object,
		mode: String, // standalone, compact
		readonly: {
			type: Boolean,
			default: false
		}
	},
	data () {
		return {
			selected: false,
			showingAvatarCard: false,
			editing: false,
			showDeletePrompt: false,
			reactionTooltip: null,
			getEmojiDataFromNative,
			nativeEmojiToStyle
		}
	},
	computed: {
		...mapState(['user']),
		...mapState('chat', ['usersLookup']),
		...mapGetters(['hasPermission']),
		isSystemMessage () {
			return this.message.event_type !== 'channel.message'
		},
		avatarSize () {
			if (this.message.event_type === 'channel.member') {
				return 20
			} else if (this.mode === 'standalone') {
				return 36
			}
			return 28
		},
		sender () {
			return this.usersLookup[this.message.sender] || {id: this.message.sender, badges: {}}
		},
		senderDisplayName () {
			return this.sender.profile?.display_name ?? this.message.sender ?? '(unknown user)'
		},
		timestamp () {
			const timestamp = moment(this.message.timestamp)
			if (this.previousMessage && timestamp.isSame(this.previousMessage.timestamp, 'day')) {
				return timestamp.format(TIME_FORMAT)
			} else {
				return timestamp.format(DATETIME_FORMAT)
			}
		},
		shortTimestamp () {
			// The timestamp below avatars can only accommodate exactly this length
			// We don't format to HH or hh to make sure the number is the same as in timestamp above
			return moment(this.message.timestamp).format(TIME_FORMAT).split(' ')[0]
		},
		content () {
			return generateHTML(this.message.content?.body)
		},
		mergeWithPreviousMessage () {
			return this.previousMessage && !this.isSystemMessage && this.previousMessage.event_type === 'channel.message' && this.previousMessage.sender === this.message.sender && moment(this.message.timestamp).diff(this.previousMessage.timestamp, 'minutes') < 15
		},
		mergeWithNextMessage () {
			return this.nextMessage && !this.isSystemMessage && this.nextMessage.event_type === 'channel.message' && this.nextMessage.sender === this.message.sender && moment(this.nextMessage.timestamp).diff(this.message.timestamp, 'minutes') < 15
		}
	},
	methods: {
		addReaction (emoji) {
			this.$store.dispatch('chat/addReaction', {message: this.message, reaction: emoji.native})
		},
		toggleReaction (emoji, users) {
			if (users.includes(this.user.id)) {
				if (users.length === 1) {
					this.reactionTooltip = null
				}
				this.$store.dispatch('chat/removeReaction', {message: this.message, reaction: emoji})
			} else {
				this.$store.dispatch('chat/addReaction', {message: this.message, reaction: emoji})
			}
		},
		async initReactionTooltip (event, {emoji, users}) {
			this.reactionTooltip = {
				emoji,
				// TODO 'and you'
				usersString: users.map(u => this.usersLookup[u]?.profile?.display_name || '???').join(', ')
			}
			await this.$nextTick()
			createPopper(event.target, this.$refs.reactionTooltip, {
				placement: 'top',
				strategy: 'fixed',
				modifiers: [
					{name: 'offset', options: {offset: [0, 8]}},
					{name: 'arrow', options: {padding: 4}}
				],
			})
		},
		startEditingMessage () {
			this.selected = false
			this.editing = true
		},
		editMessage (content) {
			this.editing = false
			this.$store.dispatch('chat/editMessage', {message: this.message, content})
		},
		deleteMessage () {
			this.$store.dispatch('chat/deleteMessage', this.message)
			this.showDeletePrompt = false
		},
		async showAvatarCard (event) {
			this.showingAvatarCard = true
			await this.$nextTick()
			createPopper(this.$refs.avatar.$el, this.$refs.avatarCard.$refs.card, {
				placement: 'right-start',
				modifiers: [{
					name: 'flip',
					options: {
						flipVariations: false
					}
				}, {
					name: 'preventOverflow',
					options: {
						padding: 8
					}
				}]
			})
		}
	}
}
</script>
<style lang="stylus">
.c-chat-message
	flex: none
	display: flex
	padding: 4px 8px
	position: relative
	min-height: 48px
	box-sizing: border-box
	&:hover, .selected
		background-color: $clr-grey-100
	&.readonly
		pointer-events: none
	.timestamp
		font-size: 11px
		color: $clr-secondary-text-light
	.avatar-column
		flex: none
		width: 28px
		display: flex
		justify-content: flex-end
		// TODO check 12h size
		.timestamp
			margin-top: 15.5px // HACK
			line-height: 0
	.content-wrapper
		flex: auto
		min-width: 0
		margin-left: 8px
		padding-top: 6px // ???
		overflow-wrap: break-word
		.message-header
			display: flex
			align-items: baseline
		.content
			white-space: pre-wrap
			.files
				margin-top: 8px
			.chat-image
				max-width: calc(100% - 32px)
				max-height: 300px
		.content, .reactions
			.emoji
				vertical-align: bottom
				line-height: 20px
				width: 20px
				height: 20px
				display: inline-block
				background-image: url("~emoji-datasource-twitter/img/twitter/sheets-256/64.png")
				background-size: 5700% 5700%
				image-rendering: -webkit-optimize-contrast
		.call
			border: border-separator()
			border-radius: 6px
			align-self: flex-start
			padding: 16px
			margin-top: 8px
			display: flex
			flex-direction: column
			.bunt-button
				themed-button-primary()
				margin-top: 16px
				align-self: flex-end
		.preview-card
			display: block
			border: border-separator()
			border-radius: 4px
			max-width: 520px
			align-self: flex-start
			margin: 8px 0 4px 0
			padding: 8px
			color: $clr-primary-text-light
			background-color: $clr-white
			&:hover
				color: var(--clr-primary)
				background-color: $clr-grey-100
				.url
					color: var(--clr-primary)
			.url
				color: $clr-disabled-text-light
				font-weight: 500
				font-size: 12px
			img
				max-width: 100%
				object-fit: contain
				max-height: 400px
			.title
				font-size: 16px
				font-weight: 500
				margin: 4px 0
			.description
				white-space: pre-wrap
	.reactions
		display: flex
		flex-wrap: wrap
		.reaction, .btn-emoji-picker
			display: flex
			align-items: center
			border: 1px solid rgba(25,25,25,.04)
			background-color: rgba(29,29,29,.04)
			border-radius: 16px
			padding: 4px
			margin-right: 4px
			cursor: pointer
			&:hover
				border: border-separator()
				background-color: $clr-white
			&.reacted-by-me
				border: 1px solid var(--clr-primary)
				background-color: var(--clr-primary-alpha-18)
			.emoji
				height: 16px
				width: @height
				line-height: @height
			.count
				font-size: 12px
				margin: 0 4px 0 8px
		.btn-emoji-picker
			height: 18px
			width: @height
			padding: 2px 6px 4px 8px
			box-sizing: content-box
			svg
				width: 18px
				height: 18px
		.reaction-tooltip
			background-color: $clr-blue-grey-900
			color: $clr-primary-text-dark
			padding: 12px 8px 8px
			border-radius: 4px
			display: flex
			flex-direction: column
			align-items: center
			max-width: 180px
			z-index: 820
			.emoji-wrapper
				background-color: $clr-white
				padding: 4px
				border-radius: 4px
				margin-bottom: 8px
				.emoji
					height: 36px
					width: @height
					line-height: @height
			.description
				text-align: center
			.users
				font-weight: 600
			.emoji-text
				font-style: italic
			.arrow
				background-color: $clr-blue-grey-900
				height: 6px
				width: 12px
			&[data-popper-placement^='top'] > .arrow
				bottom: -6px
				clip-path: polygon(0 0, calc(50%) 100%, calc(50%) 100%, 100% 0)
			&[data-popper-placement^='bottom'] > .arrow
				top: -6px
				clip-path: polygon(0 100%, calc(50%) 0, calc(50%) 0, 100% 100%)

	.c-chat-input
		background-color: $clr-white
	.system-content
		color: $clr-secondary-text-light
		margin-left: 8px
		line-height: 20px
	.c-avatar
		cursor: pointer
	.display-name
		font-weight: 600
		margin-right: 4px
		&:hover
			text-decoration: underline
			cursor: pointer
	&:not(:hover):not(.selected)
		& > .actions
			visibility: hidden
		.avatar-column .timestamp
			visibility: hidden
	> .actions
		// HACK popper.js seems to die with this https://github.com/popperjs/popper-core/issues/1035
		// will-change: visibility
		position: absolute
		right: 4px
		top: -16px
		display: flex
		background-color: $clr-white
		border: border-separator()
		border-radius: 4px
		.bunt-icon-button
			icon-button-style(style: clear)
	.c-menu-dropdown .menu
		.delete-message
			color: $clr-danger
			&:hover
				background-color: $clr-danger
				color: $clr-primary-text-dark
	.delete-message-prompt
		.prompt-wrapper
			width: auto
			min-width: 480px
			max-width: 780px
		.prompt-content
			padding: 16px
			display: flex
			flex-direction: column
		.message-to-delete-wrapper
			border: border-separator()
			border-radius: 4px
			padding: 8px
		.actions
			display: flex
			align-self: flex-end
			margin-top: 16px
		#btn-cancel
			button-style(style: clear)
			margin-right: 8px
		#btn-delete-message
			button-style(color: $clr-danger)
	&.system-message
		min-height: 28px
		.c-avatar
			margin-right: 4px
	&.standalone
		padding-left: 16px
		.avatar-column
			width: 36px
			.timestamp
				margin-top: 13.5px // HACK
		.content-wrapper
			padding-top: 4px
			display: flex
			flex-direction: column
			.message-header
				padding-bottom: 4px
	&.compact
		min-height: 36px
		.message-header
			display: inline-flex
			.timestamp
				margin-right: 4px
		.content
			display: inline
		.actions
			right: 4px
			top: 2px
			.bunt-icon-button
				height: 32px
				width: @height
				.bunt-icon
					font-size: 16px
					height: 24px
					line-height: @height
	&.merge-with-next-message:not(.merge-with-previous-message)
		padding-bottom: 0
		min-height: 0
	&.merge-with-previous-message
		padding-top: 0
		min-height: 0
</style>

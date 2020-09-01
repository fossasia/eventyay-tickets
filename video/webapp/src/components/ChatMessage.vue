<template lang="pug">
.c-chat-message(:class="[mode, {selected, 'system-message': isSystemMessage, 'merge-with-previous-message': mergeWithPreviousMessage, 'merge-with-next-message': mergeWithNextMessage}]")
	.avatar-column
		avatar(v-if="!mergeWithPreviousMessage", :user="sender", :size="avatarSize", @click.native="showAvatarCard", ref="avatar")
		.timestamp(v-if="mergeWithPreviousMessage") {{ timestamp }}
	template(v-if="message.event_type === 'channel.message'")
		.content-wrapper
			.message-header(v-if="!mergeWithPreviousMessage")
				.display-name(@click="showAvatarCard") {{ senderDisplayName }}
					|
					.user-badge(v-for="b in sender.badges") {{ b }}
				.timestamp {{ timestamp }}
			template(v-if="message.content.type === 'text'")
				chat-input(v-if="editing", :message="message", @send="editMessage")
				.content(v-else, v-html="content")
			.call(v-else-if="message.content.type === 'call'")
				.prompt(v-if="message.sender === user.id") You started a video call
				.prompt(v-else) {{ senderDisplayName }} invited you to a video call
				bunt-button(@click="$store.dispatch('chat/joinCall', message.content.body.id)") Join
		.actions
			menu-dropdown(v-if="$features.enabled('chat-moderation') && (hasPermission('room:chat.moderate') || message.sender === user.id)", v-model="selected")
				template(v-slot:button="{toggle}")
					bunt-icon-button(@click="toggle") dots-vertical
				template(v-slot:menu)
					.edit-message(v-if="message.sender === user.id", @click="startEditingMessage") {{ $t('ChatMessage:message-edit:label') }}
					.delete-message(@click="selected = false, showDeletePrompt = true") {{ $t('ChatMessage:message-delete:label') }}
	template(v-else-if="message.event_type === 'channel.member'")
		.system-content {{ sender.profile ? sender.profile.display_name : message.sender }} {{ message.content.membership === 'join' ? $t('ChatMessage:join-message:text') : $t('ChatMessage:leave-message:text') }}
	chat-user-card(v-if="showingAvatarCard", ref="avatarCard", :sender="sender", @close="showingAvatarCard = false")
	prompt.delete-message-prompt(v-if="showDeletePrompt", @close="showDeletePrompt = false")
		.prompt-content
			h2 Delete this message?
			.message
				.avatar-column
					avatar(:user="sender", :size="avatarSize")
				.content-wrapper
					.message-header
						.display-name {{ senderDisplayName }}
						.timestamp {{ timestamp }}
					.content(v-html="content")
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
import { markdownEmoji } from 'lib/emoji'
import { createPopper } from '@popperjs/core'
import Avatar from 'components/Avatar'
import ChatInput from 'components/ChatInput'
import ChatUserCard from 'components/ChatUserCard'
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
	components: { Avatar, ChatInput, ChatUserCard, MenuDropdown, Prompt },
	props: {
		message: Object,
		previousMessage: Object,
		nextMessage: Object,
		mode: String
	},
	data () {
		return {
			selected: false,
			showingAvatarCard: false,
			editing: false,
			showDeletePrompt: false
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
			return this.sender.profile?.display_name ?? this.message.sender
		},
		timestamp () {
			const timestamp = moment(this.message.timestamp)
			if (this.previousMessage && timestamp.isSame(this.previousMessage.timestamp, 'day')) {
				return timestamp.format(TIME_FORMAT)
			} else {
				return timestamp.format(DATETIME_FORMAT)
			}
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
		startEditingMessage () {
			this.selected = false
			this.editing = true
		},
		editMessage (newBody) {
			this.editing = false
			this.$store.dispatch('chat/editMessage', {message: this.message, newBody})
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
		overflow-wrap: anywhere
		.message-header
			display: flex
			align-items: baseline
		.content
			white-space: pre-wrap
			.emoji
				vertical-align: bottom
				line-height: 20px
				width: 20px
				height: 20px
				display: inline-block
				background-image: url("~emoji-datasource-twitter/img/twitter/sheets-256/64.png")
				background-size: 5700% 5700%
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
		will-change: visibility
		position: absolute
		right: 4px
		top: 6px
		display: flex
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
		.message
			border: border-separator()
			padding: 8px
			display: flex
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
		.avatar-column
			width: 36px
			.timestamp
				margin-top: 13.5px // HACK
		.content-wrapper
			padding-top: 4px
			display: flex
			flex-direction: column
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
		.actions
			top: -2px
</style>

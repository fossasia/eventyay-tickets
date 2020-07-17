<template lang="pug">
.c-chat-message(:class="[mode, {selected, 'system-message': isSystemMessage}]")
	.avatar-column
		avatar(:user="sender", :size="avatarSize", @click.native="showAvatarCard", ref="avatar")
	template(v-if="message.event_type === 'channel.message'")
		.content-wrapper
			.message-header(v-if="mode === 'standalone'")
				.display-name(@click="showAvatarCard") {{ senderDisplayName }}
				.timestamp {{ timestamp }}
			.display-name(v-else) {{ senderDisplayName }}
			template(v-if="message.content.type === 'text'")
				chat-input(v-if="editing", :message="message", @send="editMessage")
				.content(v-else, v-html="content")
			.call(v-else-if="message.content.type === 'call'")
				.prompt {{ senderDisplayName }} invited you to a video call
				bunt-button(@click="$store.dispatch('chat/joinCall', message.content.body.id)") Join
		.actions
			bunt-icon-button(v-if="$features.enabled('chat-moderation') && (hasPermission('room:chat.moderate') || message.sender === user.id)", @click="showMenu") dots-vertical
	template(v-else-if="message.event_type === 'channel.member'")
		.system-content {{ sender.profile ? sender.profile.display_name : message.sender }} {{ message.content.membership === 'join' ? $t('ChatMessage:join-message:text') : $t('ChatMessage:leave-message:text') }}
	//- intercepts all events
	.menu-blocker(v-if="selected || showingAvatarCard", @click="selected = false, showingAvatarCard = false")
	.menu(v-if="selected", ref="menu")
		.edit-message(v-if="message.sender === user.id", @click="startEditingMessage") {{ $t('ChatMessage:message-edit:label') }}
		.delete-message(@click="deleteMessage") {{ $t('ChatMessage:message-delete:label') }}
	chat-user-card(v-if="showingAvatarCard", ref="avatarCard", :sender="sender")
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

const DATETIME_FORMAT = 'DD.MM. HH:mm'
const TIME_FORMAT = 'HH:mm'

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
	props: {
		message: Object,
		mode: String
	},
	components: { Avatar, ChatInput, ChatUserCard },
	data () {
		return {
			selected: false,
			showingAvatarCard: false,
			editing: false
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
			return this.usersLookup[this.message.sender] || {id: this.message.sender}
		},
		senderDisplayName () {
			return this.sender.profile?.display_name ?? this.message.sender
		},
		timestamp () {
			const timestamp = moment(this.message.timestamp)
			if (timestamp.isSame(moment(), 'day')) {
				return timestamp.format(TIME_FORMAT)
			} else {
				return timestamp.format(DATETIME_FORMAT)
			}
		},
		content () {
			return generateHTML(this.message.content?.body)
		}
	},
	methods: {
		async showMenu (event) {
			this.selected = true
			await this.$nextTick()
			const button = event.target.closest('.bunt-icon-button')
			createPopper(button, this.$refs.menu, {
				placement: 'left-start'
			})
		},
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
			this.selected = false
		},
		async showAvatarCard (event) {
			this.showingAvatarCard = true
			await this.$nextTick()
			createPopper(this.$refs.avatar.$el, this.$refs.avatarCard.$el, {
				placement: 'right-start',
				modifiers: [{
					name: 'flip',
					options: {
						flipVariations: false
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
	.avatar-column
		flex: none
		width: 28px
		display: flex
		justify-content: flex-end
	.content-wrapper
		flex: auto
		min-width: 0
		margin-left: 8px
		padding-top: 6px // ???
		overflow-wrap: anywhere
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
	&:not(:hover):not(.selected) > .actions
		visibility: hidden
	> .actions
		will-change: visibility
		position: absolute
		right: 4px
		top: 6px
		display: flex
		.bunt-icon-button
			icon-button-style(style: clear)
	.menu-blocker
		position: fixed
		top: 0
		left: 0
		width: 100vw
		height: var(--vh100)
		z-index: 4999
	.menu
		card()
		z-index: 5000
		display: flex
		flex-direction: column
		min-width: 240px
		padding: 4px 0
		> *
			flex: none
			height: 32px
			font-size: 16px
			line-height: 32px
			padding: 0 0 0 16px
			cursor: pointer
			user-select: none
			&:hover
				background-color: var(--clr-input-primary-bg)
				color: var(--clr-input-primary-fg)
			&.delete-message
				color: $clr-danger
				&:hover
					background-color: $clr-danger
					color: $clr-primary-text-dark
	&.system-message
		min-height: 28px
		.c-avatar
			margin-right: 4px
	&.standalone
		.avatar-column
			width: 36px
		.content-wrapper
			padding-top: 4px
			display: flex
			flex-direction: column
		.message-header
			display: flex
			align-items: baseline
			.timestamp
				font-size: 11px
				color: $clr-secondary-text-light
	&.compact
		min-height: 36px
		.display-name, .content
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
</style>

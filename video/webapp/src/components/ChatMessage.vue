<template lang="pug">
.c-chat-message(:class="[mode, {selected, 'system-message': isSystemMessage}]")
	.avatar-column
		avatar(:user="user", :size="avatarSize", @click.native="showAvatarCard", ref="avatar")
	template(v-if="message.event_type === 'channel.message'")
		.content-wrapper
			.message-header(v-if="mode === 'standalone'")
				.display-name(@click="showAvatarCard") {{ user.profile ? user.profile.display_name : message.sender }}
				.timestamp {{ timestamp }}
			.display-name(v-else) {{ user.profile ? user.profile.display_name : message.sender }}
			chat-input(v-if="editing", :message="message", @send="editMessage")
			.content(v-else, v-html="content")
		.actions
			bunt-icon-button(v-if="$features.enabled('chat-moderation') && hasPermission('room:chat.moderate')", @click="showMenu") dots-vertical
	template(v-else-if="message.event_type === 'channel.member'")
		.system-content {{ user.profile ? user.profile.display_name : message.sender }} {{ message.content.membership === 'join' ? $t('ChatMessage:join-message:text') : $t('ChatMessage:leave-message:text') }}
	//- intercepts all events
	.menu-blocker(v-if="selected || showingAvatarCard", @click="selected = false, showingAvatarCard = false")
	.menu(v-if="selected", ref="menu")
		.edit-message(@click="startEditingMessage") {{ $t('ChatMessage:message-edit:label') }}
		.delete-message(@click="deleteMessage") {{ $t('ChatMessage:message-delete:label') }}
	.avatar-card(v-if="showingAvatarCard", ref="avatarCard")
		avatar(:user="user", :size="128")
		.name {{ user.profile ? user.profile.display_name : this.message.sender }}
		.actions(v-if="$features.enabled('chat-moderation') && hasPermission('room:chat.moderate')")
			bunt-button#btn-ban ban
</template>
<script>
// TODO
// - cancel editing
// - handle editing error
import moment from 'moment'
import { mapState, mapGetters } from 'vuex'
import { createPopper } from '@popperjs/core'
import { getHTMLWithEmoji } from 'lib/emoji'
import Avatar from 'components/Avatar'
import ChatInput from 'components/ChatInput'

const DATETIME_FORMAT = 'DD.MM. HH:mm'
const TIME_FORMAT = 'HH:mm'

export default {
	props: {
		message: Object,
		mode: String
	},
	components: { Avatar, ChatInput },
	data () {
		return {
			selected: false,
			showingAvatarCard: false,
			editing: false
		}
	},
	computed: {
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
		user () {
			return this.usersLookup[this.message.sender] || {id: this.message.sender}
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
			return getHTMLWithEmoji(this.message.content?.body)
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
			createPopper(this.$refs.avatar.$el, this.$refs.avatarCard, {
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
		word-break: break-all
		.content .emoji
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
	.avatar-card
		card()
		z-index: 5000
		display: flex
		flex-direction: column
		padding: 8px
		.name
			font-size: 24px
			font-weight: 600
			margin-top: 8px
		.actions
			margin-top: 16px
			#btn-ban
				button-style(color: $clr-danger)
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

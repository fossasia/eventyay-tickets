<template lang="pug">
.c-chat-message(:class="[mode, {selected, 'system-message': isSystemMessage}]")
	.avatar-column
		avatar(:user="user", :size="avatarSize", @click.native="showAvatarCard", ref="avatar")
	template(v-if="message.event_type === 'channel.message'")
		.content-wrapper(v-if="mode === 'standalone'")
			.message-header
				.display-name(@click="showAvatarCard") {{ user.profile ? user.profile.display_name : message.sender }}
				.timestamp {{ timestamp }}
			.content(v-html="content")
		.content-wrapper(v-else)
			span.display-name {{ user.profile ? user.profile.display_name : message.sender }}
			span.content(v-html="content")
		.actions
			bunt-icon-button(v-if="$features.enabled('chat-moderation')", @click="showMenu") dots-vertical
	template(v-else-if="message.event_type === 'channel.member'")
		.system-content {{ user.profile ? user.profile.display_name : message.sender }} {{ message.content.membership === 'join' ? 'joined' : 'left' }}
	//- intercepts all events
	.menu-blocker(v-if="selected || showingAvatarCard", @click="selected = false, showingAvatarCard = false")
	.menu(v-if="selected", ref="menu")
		.edit-message(@click="editMessage") edit message
		.delete-message(@click="deleteMessage") delete message
	.avatar-card(v-if="showingAvatarCard", ref="avatarCard")
		avatar(:user="user", :size="128")
		.name {{ user.profile ? user.profile.display_name : this.message.sender }}
		.actions(v-if="$features.enabled('chat-moderation')")
			bunt-button#btn-ban ban
</template>
<script>
import moment from 'moment'
import { mapState } from 'vuex'
import { createPopper } from '@popperjs/core'
import EmojiRegex from 'emoji-regex'
import { getEmojiDataFromNative } from 'emoji-mart'
import emojiData from 'emoji-mart/data/twitter.json'
import { getEmojiPosition } from 'lib/emoji'
import Avatar from 'components/Avatar'

const emojiRegex = EmojiRegex()

const DATETIME_FORMAT = 'DD.MM. HH:mm'
const TIME_FORMAT = 'HH:mm'

export default {
	props: {
		message: Object,
		mode: String
	},
	components: { Avatar },
	data () {
		return {
			selected: false,
			showingAvatarCard: false
		}
	},
	computed: {
		...mapState('chat', ['usersLookup']),
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
			return this.message.content?.body?.replace(emojiRegex, match => {
				const emoji = getEmojiDataFromNative(match, 'twitter', emojiData)
				return `<span class="emoji" style="background-position: ${getEmojiPosition(emoji)}"></span>`
			})
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
		editMessage (event) {
			this.selected = false
		},
		deleteMessage (event) {
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
	display: flex
	align-items: flex-start
	padding: 4px 8px
	position: relative
	min-height: 48px
	box-sizing: border-box
	&:hover, .selected
		background-color: $clr-grey-100
	.avatar-column
		width: 28px
		display: flex
		justify-content: flex-end
	.content-wrapper
		margin-left: 8px
		padding-top: 6px // ???
		.emoji
			vertical-align: bottom
			line-height: 20px
			width: 20px
			height: 20px
			display: inline-block
			background-image: url("~emoji-datasource-twitter/img/twitter/sheets-256/64.png")
			background-size: 5700% 5700%
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

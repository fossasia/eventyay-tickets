<template lang="pug">
.c-chat-message(:class="[mode, {selected}]")
	avatar(:user="user", :size="mode === 'standalone' ? 36 : 28")
	.content-wrapper(v-if="mode === 'standalone'")
		.message-header
			.display-name {{ user.profile ? user.profile.display_name : this.message.sender }}
			.timestamp {{ timestamp }}
		.content(v-html="content")
	.content-wrapper(v-else)
		span.display-name {{ user.profile ? user.profile.display_name : this.message.sender }}
		span.content(v-html="content")
	.actions
		bunt-icon-button(@click="showMenu") dots-vertical
	//- intercepts all events
	.menu-blocker(v-if="selected", @click="selected = false")
	.menu(v-if="selected", ref="menu")
		.delete-message(@click="deleteMessage") delete message
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
			selected: false
		}
	},
	computed: {
		...mapState('chat', ['usersLookup']),
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
				placement: 'left'
			})
		},
		deleteMessage (event) {
			console.log(event)
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
	.content-wrapper
		margin-left: 8px
		padding-top: 6px // ???
		.emoji
			vertical-align: bottom
			line-height: 20px
			width: 20px
			height: 20px
			display: inline-block
			background-image: url("https://unpkg.com/emoji-datasource-twitter@5.0.1/img/twitter/sheets-256/64.png")
			background-size: 5700% 5700%
	.display-name
		font-weight: 600
		// color: $clr-secondary-text-light
		margin-right: 4px
	&:not(:hover):not(.selected) .actions
		display: none
	.actions
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
		height: 100vh
		z-index: 4999
	.menu
		card()
		z-index: 5000
		display: flex
		flex-direction: column
		min-width: 240px
		> *
			flex: none
			height: 32px
			font-size: 16px
			line-height: 32px
			padding: 0 0 0 16px
			cursor: pointer
			user-select: none
			&:hover
				background-color: $clr-primary
				color: $clr-primary-text-dark
			&.delete-message
				color: $clr-danger
				&:hover
					background-color: $clr-danger
					color: $clr-primary-text-dark
	&.standalone
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
</style>

<template lang="pug">
.c-chat-message(:class="[mode]")
	avatar(:user="user", :size="mode === 'standalone' ? 36 : 28")
	.content-wrapper(v-if="mode === 'standalone'")
		.message-header
			.display-name {{ user.profile ? user.profile.display_name : this.message.sender }}
			.timestamp {{ timestamp }}
		.content(v-html="content")
	.content-wrapper(v-else)
		span.display-name {{ user.profile ? user.profile.display_name : this.message.sender }}
		span.content(v-html="content")
</template>
<script>
import moment from 'moment'
import { mapState } from 'vuex'
import EmojiRegex from 'emoji-regex'
import { getEmojiDataFromNative } from 'emoji-mart'
import emojiData from 'emoji-mart/data/twitter.json'
import { getEmojiPosition } from 'lib/emoji'
import Avatar from 'components/Avatar'

const emojiRegex = EmojiRegex()

const DATETIME_FORMAT = 'dd.MM. HH:mm'
const TIME_FORMAT = 'HH:mm'

export default {
	props: {
		message: Object,
		mode: String
	},
	components: { Avatar },
	data () {
		return {
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
	}
}
</script>
<style lang="stylus">
.c-chat-message
	display: flex
	align-items: flex-start
	padding: 4px 8px
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

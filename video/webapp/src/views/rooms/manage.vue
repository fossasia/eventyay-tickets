<template lang="pug">
.c-room-manager
	.ui-page-header.room-info(v-if="!modules['page.markdown'] && !modules['page.landing']")
		.room-name {{ room.name }}
	.main
		.schedule
			h3 Schedule?
		.polls
			.header
				h3 Polls
				bunt-icon-button(@click="showUrlPopup('polls')") presentation
			p Coming Soon
		.questions
			.header
				h3 Questions
				bunt-icon-button(@click="showUrlPopup('questions')") presentation
			questions(v-if="modules['question']", :module="modules['question']")
		.chat
			.header
				h3 Chat
				bunt-icon-button(@click="showUrlPopup('chat')") presentation
			chat(v-if="modules['chat.native']", :room="room", :module="modules['chat.native']", mode="compact", :key="room.id")
	.ui-background-blocker(v-if="showPresentationUrlFor", @click="showPresentationUrlFor = null")
	.url-popup(v-if="showPresentationUrlFor", ref="urlPopup", :class="{'url-copied': copiedUrl}")
		.copy-success(v-if="copiedUrl") Copied!
		template(v-else)
			.copy-url
				bunt-input(ref="urlInput", name="presentation-url", :readonly="true", :value="getPresentationUrl(showPresentationUrlFor)")
				bunt-button(@click="copyUrl") Copy
			.hint This url contains your personal token.
				br
				| Don't make this url publicly accessible!
</template>
<script>
import {mapGetters, mapState} from 'vuex'
import { createPopper } from '@popperjs/core'
import Chat from 'components/Chat'
import Prompt from 'components/Prompt'
import Questions from 'components/Questions'

export default {
	name: 'RoomManager',
	components: { Chat, Prompt, Questions },
	props: {
		roomId: String
	},
	data () {
		return {
			showPresentationUrlFor: null,
			copiedUrl: false
		}
	},
	computed: {
		...mapState(['world', 'rooms', 'token']),
		...mapGetters('schedule', ['sessions', 'sessionsScheduledNow']),
		room () {
			if (this.roomId === undefined) return this.rooms[0] // '/' is the first room
			return this.rooms.find(room => room.id === this.roomId)
		},
		modules () {
			return this.room?.modules.reduce((acc, module) => {
				acc[module.type] = module
				return acc
			}, {})
		},
	},
	methods: {
		async showUrlPopup (type) {
			this.showPresentationUrlFor = type
			await this.$nextTick()
			createPopper(event.target, this.$refs.urlPopup, {
				placement: 'bottom-end',
				modifiers: [
					{name: 'offset', options: {offset: [16, 12]}}
				]
			})
		},
		getPresentationUrl (type) {
			return window.location.origin + this.$router.resolve({name: 'presentation-mode', params: {type}}).href + '#token=' + this.token
		},
		copyUrl () {
			this.$refs.urlInput.$refs.input.select()
			document.execCommand('copy')
			this.copiedUrl = true
			setTimeout(() => {
				this.copiedUrl = false
				this.showPresentationUrlFor = null
			}, 600)
		}
	}
}
</script>
<style lang="stylus">
.c-room-manager
	display: flex
	flex-direction: column
	min-height: 0
	background-color: $clr-white
	.room-info
		padding: 0 24px
		height: 56px
		align-items: baseline
		.room-name
			font-size: 24px
			line-height: 56px
			font-weight: 600
			display: flex
			flex-direction: column
		.room-session
			margin-left: 8px
			font-size: 18px
	.main
		display: flex
		min-height: 0
	.schedule
		flex: auto
		margin-top: 360px
		padding: 16px
		h3
			margin: 0
	.chat, .questions, .polls
		display: flex
		flex-direction: column
		min-height: 0
		width: var(--chatbar-width)
		flex: none
		border-left: border-separator()
		.header
			display: flex
			justify-content: space-between
			align-items: center
			height: 56px
			border-bottom: border-separator()
			padding: 0 16px
			.bunt-icon-button
				icon-button-style(style: clear)
		.c-chat
			min-height: 0
	.polls p
		text-align: center

	.url-popup
		card()
		display: flex
		flex-direction: column
		justify-content: center
		align-items: center
		width: var(--chatbar-width)
		height: 140px
		z-index: 1000
		transition: background-color .2s ease
		.copy-url
			display: flex
			align-items: center
			gap: 8px
			margin-bottom: 16px
			.bunt-input
				input-style(size: compact)
				padding: 0
				flex: auto
			.bunt-button
				themed-button-primary()
				flex: none
		.hint
			text-align: center
			color: $clr-secondary-text-light
		&.url-copied
			background-color: $clr-success
			color: $clr-primary-text-dark
		.copy-success
			font-size: 24px
			font-weight: 500
</style>

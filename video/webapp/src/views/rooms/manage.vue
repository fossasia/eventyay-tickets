<template lang="pug">
.c-room-manager
	.ui-page-header.room-info(v-if="!modules['page.markdown'] && !modules['page.landing']")
		.room-name {{ room.name }}
		.room-session(v-if="currentSession") {{ currentSession.title }}
	.main
		.schedule
			h3 Schedule?
		.polls
			.header
				h3 Polls
				bunt-icon-button presentation
			p Sorry, no polls yet
		.questions
			.header
				h3 Questions
				bunt-icon-button presentation
			questions(v-if="modules['question']", :module="modules['question']")
		.chat
			.header
				h3 Chat
				bunt-icon-button presentation
			chat(v-if="modules['chat.native']", :room="room", :module="modules['chat.native']", mode="compact", :key="room.id")
</template>
<script>
import {mapGetters, mapState} from 'vuex'
import Chat from 'components/Chat'
import Questions from 'components/Questions'

export default {
	name: 'RoomManager',
	components: { Chat, Questions },
	props: {
		roomId: String
	},
	data () {
		return {
		}
	},
	computed: {
		...mapState(['world', 'rooms']),
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
	created () {},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {}
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
</style>

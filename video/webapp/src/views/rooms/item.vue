<template lang="pug">
.c-room(v-if="room", :class="{'standalone-chat': modules['chat.native'] && room.modules.length === 1}")
	.main
		.room-info
			img(v-if="room.picture", :src="room.picture")
			.room-info-wrapper
				.room-info-text
					h2 {{ room.name }}
					.description {{ room.description }}
				.talk-info(v-if="currentTalk")
					.current-talk Current talk
					h3 {{ currentTalk.title }}
		livestream(v-if="modules['livestream.native'] && streamingRoom !== room", :room="room", :module="modules['livestream.native']")
		.livestream-placeholder(v-else-if="modules['livestream.native']")
		big-blue-button(v-else-if="modules['call.bigbluebutton']", :room="room", :module="modules['call.bigbluebutton']")
		reactions-overlay(v-if="modules['livestream.native']")
		.stage-tool-blocker(v-if="activeStageTool !== null", @click="activeStageTool = null")
		.stage-tools(v-if="modules['livestream.native']")
			.stage-tool(:class="{active: activeStageTool === 'qa'}", @click="activeStageTool = 'qa'") Ask a question
			reactions-bar(:expanded="activeStageTool === 'reaction'", @expand="activeStageTool = 'reaction'")
	chat(v-if="modules['chat.native']", :room="room", :module="modules['chat.native']", :mode="room.modules.length === 1 ? 'standalone' : 'compact'", :key="room.id")
	slot(v-if="streamingRoom && streamingRoom !== room")
</template>
<script>
import { mapState } from 'vuex'
import moment from 'moment'
import BigBlueButton from 'components/BigBlueButton'
import Chat from 'components/Chat'
import Livestream from 'components/Livestream'
import ReactionsBar from 'components/ReactionsBar'
import ReactionsOverlay from 'components/ReactionsOverlay'

export default {
	name: 'room',
	props: {
		roomId: String
	},
	components: { BigBlueButton, Chat, Livestream, ReactionsBar, ReactionsOverlay },
	data () {
		return {
			activeStageTool: null // reaction, qa
		}
	},
	computed: {
		...mapState(['connected', 'world', 'schedule', 'streamingRoom']),
		room () {
			return this.$store.state.rooms.find(room => room.id === this.roomId)
		},
		modules () {
			return this.room?.modules.reduce((acc, module) => {
				acc[module.type] = module
				return acc
			}, {})
		},
		scheduleRoom () {
			if (!this.schedule || !this.world.pretalx?.room_mapping) return
			const scheduleDay = this.schedule.schedule.find(day => moment().isSame(day.start, 'day'))
			if (!scheduleDay) return
			const roomId = Number(Object.entries(this.world.pretalx.room_mapping).find(mapping => mapping[1] === this.room.id)?.[0])
			return scheduleDay.rooms.find(room => room.id === roomId)
		},
		currentTalk () {
			if (!this.scheduleRoom) return
			return this.scheduleRoom.talks.find(talk => moment().isBetween(talk.start, talk.end))
		}
	},
	watch: {
		connected (value) {
			if (value) {
				// re-enter
				this.$store.dispatch('enterRoom', this.room)
			}
		}
	},
	created () {
		// TODO decouple from component lifecycle
		this.$store.dispatch('enterRoom', this.room)
	},
	beforeDestroy () {
		this.$store.dispatch('leaveRoom', this.room)
	},
}
</script>
<style lang="stylus">
.c-room
	flex: auto
	display: flex
	background-color: $clr-white
	min-height: 0
	.main
		flex: auto
		display: flex
		flex-direction: column
		min-height: 0
	.room-info
		flex: none
		display: flex
		padding: 8px
		height: 56px
		box-sizing: border-box
		img
			height: 48px
		.room-info-wrapper
			display: flex
			flex-direction: column
			margin-left: 16px
		.room-info-text
			display: flex
			align-items: center
			h2
				margin: 0 8px 0 0
		.talk-info
			display: flex
			align-items: center
			.current-talk
				text-transform: uppercase
				color: $clr-secondary-text-light
				font-size: 18px
				font-weight: 300
				line-height: 20px
			h3
				font-size: 20px
				font-weight: 500
				line-height: 20px
				margin: 0 0 0 4px
	.livestream-placeholder
		flex: auto
	.stage-tools
		flex: none
		display: flex
		height: 56px
		justify-content: flex-end
		align-items: center
		user-select: none
		overflow: hidden
		.stage-tool
			font-size: 16px
			color: $clr-secondary-text-light
			margin-right: 16px
			cursor: pointer
			padding: 8px
			position: relative
			&:hover
				border-radius: 4px
				background-color: $clr-grey-100
			&.active::before
				position: absolute
				bottom: 6px
				content: ''
				display: block
				height: 2px
				width: calc(100% - 16px)
				background-color: $clr-primary
	.stage-tool-blocker
		position: fixed
		top: 0
		left: 0
		width: 100vw
		height: 100vh
		z-index: 4999
	&.standalone-chat
		flex-direction: column
		.main
			flex: none
	&:not(.standalone-chat)
		.c-chat
			border-left: border-separator()
			flex: none
			width: var(--chatbar-width)
	+below('s')
		flex-direction: column
		.main
			flex: 1 0 auto
		.c-livestream
			height: 40vh
			flex: none
		&:not(.standalone-chat)
			.c-chat
				flex: auto
				width: 100vw
				min-height: 0
</style>

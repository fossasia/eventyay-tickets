<template lang="pug">
.c-room(v-if="room", :class="{'standalone-chat': modules['chat.native'] && room.modules.length === 1}")
	.room-info(v-if="!modules['page.markdown']")
		img(v-if="room.picture", :src="room.picture")
		.room-info-wrapper
			.room-info-text
				h2 {{ room.name }}
				.description {{ room.description }}
			.talk-info(v-if="currentTalk")
				.current-talk Current talk
				h3 {{ currentTalk.title }}
	.main
		.stage(v-if="modules['livestream.native']")
			.livestream-placeholder
			reactions-overlay(v-if="modules['livestream.native']")
			.stage-tool-blocker(v-if="activeStageTool !== null", @click="activeStageTool = null")
			.stage-tools(v-if="modules['livestream.native']")
				.stage-tool(v-if="$features.enabled('questions-answers')", :class="{active: activeStageTool === 'qa'}", @click="activeStageTool = 'qa'") Ask a question
				reactions-bar(:expanded="activeStageTool === 'reaction'", @expand="activeStageTool = 'reaction'")
		markdown-page(v-else-if="modules['page.markdown']", :module="modules['page.markdown']")
		iframe-page(v-else-if="modules['page.iframe']", :module="modules['page.iframe']")
		exhibition(v-else-if="modules['exhibition.native']", :room="room")
		chat(v-if="modules['chat.native']", :module="modules['chat.native']", :mode="room.modules.length === 1 ? 'standalone' : 'compact'", :key="room.id")
</template>
<script>
import { mapState } from 'vuex'
import moment from 'moment'
import Chat from 'components/Chat'
import Livestream from 'components/Livestream'
import MarkdownPage from 'components/MarkdownPage'
import IframePage from 'components/IframePage'
import Exhibition from 'components/Exhibition'
import ReactionsBar from 'components/ReactionsBar'
import ReactionsOverlay from 'components/ReactionsOverlay'

export default {
	name: 'room',
	props: {
		roomId: String
	},
	components: { Chat, Exhibition, Livestream, MarkdownPage, IframePage, ReactionsBar, ReactionsOverlay },
	data () {
		return {
			activeStageTool: null // reaction, qa
		}
	},
	computed: {
		...mapState(['connected', 'world', 'rooms', 'schedule']),
		room () {
			if (this.roomId === undefined) return this.rooms[0] // '/' is the first room
			return this.$store.state.rooms.find(room => room.id === this.roomId)
		},
		modules () {
			return this.room?.modules.reduce((acc, module) => {
				acc[module.type] = module
				return acc
			}, {})
		},
		scheduleRoom () {
			if (!this.schedule || !this.world.pretalx?.base_url) return
			const scheduleDay = this.schedule.schedule.find(day => moment().isSame(day.start, 'day'))
			if (!scheduleDay) return
			const roomId = this.room.pretalx_id
			if (!roomId) return
			return scheduleDay.rooms.find(room => room.id === roomId)
		},
		currentTalk () {
			if (!this.scheduleRoom) return
			return this.scheduleRoom.talks.find(talk => moment().isBetween(talk.start, talk.end))
		}
	}
}
</script>
<style lang="stylus">
.c-room
	flex: auto
	display: flex
	flex-direction: column
	background-color: $clr-white
	min-height: 0
	.main
		flex: auto
		display: flex
		min-height: 0
	.room-info
		flex: none
		display: flex
		padding: 8px
		height: 56px
		box-sizing: border-box
		border-bottom: border-separator()
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
	.stage
		display: flex
		flex-direction: column
		min-height: 0
		flex: auto
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
				background-color: var(--clr-primary)
	.stage-tool-blocker
		position: fixed
		top: 0
		left: 0
		width: 100vw
		height: var(--vh100)
		z-index: 4999
	&.standalone-chat
		.main
			flex: auto
	&:not(.standalone-chat)
		.c-chat
			border-left: border-separator()
			flex: none
			width: var(--chatbar-width)
	+below('m')
		.main
			flex-direction: column
		.stage
			flex: none
		.livestream-placeholder
			height: 40vh
			flex: none
		&:not(.standalone-chat)
			.c-chat
				flex: auto
				width: 100vw
				min-height: 0
</style>

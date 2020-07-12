<template lang="pug">
.c-room(v-if="room", :class="{'standalone-chat': modules['chat.native'] && room.modules.length === 1}")
	.room-info(v-if="!modules['page.markdown']")
		.room-name {{ room.name }}
		.room-session(v-if="currentSession") {{ currentSession.title }}
		bunt-icon-button(@click="showEditSchedule = true") calendar_edit
		bunt-icon-button(@click="showRecordingsPrompt = true", :tooltip="$t('Room:recordings:tooltip')", tooltipPlacement="left", v-if="modules['call.bigbluebutton'] && hasPermission('room:bbb.recordings')") file-video-outline
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
		chat(v-if="modules['chat.native']", :module="modules['chat.native']", :mode="room.modules.length === 1 ? 'standalone' : 'compact'", :key="room.id")
	transition(name="prompt")
		recordings-prompt(:room="room", v-if="showRecordingsPrompt", @close="showRecordingsPrompt = false")
	edit-room-schedule(v-if="showEditSchedule", :room="room", :currentSession="currentSession", @close="showEditSchedule = false")
</template>
<script>
import {mapGetters, mapState} from 'vuex'
import moment from 'moment'
import EditRoomSchedule from './EditRoomSchedule'
import Chat from 'components/Chat'
import Livestream from 'components/Livestream'
import MarkdownPage from 'components/MarkdownPage'
import IframePage from 'components/IframePage'
import ReactionsBar from 'components/ReactionsBar'
import ReactionsOverlay from 'components/ReactionsOverlay'
import RecordingsPrompt from 'components/RecordingsPrompt'

export default {
	name: 'room',
	props: {
		roomId: String
	},
	components: { EditRoomSchedule, Chat, Livestream, MarkdownPage, IframePage, ReactionsBar, ReactionsOverlay, RecordingsPrompt },
	data () {
		return {
			showRecordingsPrompt: false,
			showEditSchedule: false,
			activeStageTool: null // reaction, qa
		}
	},
	computed: {
		...mapGetters(['hasPermission']),
		...mapState(['connected', 'world', 'rooms', 'schedule']),
		...mapGetters(['flatSchedule', 'sessionsScheduledNow']),
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
		currentSession () {
			let session
			if (this.room.schedule_data) {
				session = this.flatSchedule?.sessions.find(session => session.id === this.room.schedule_data.session)
			}
			if (!session) {
				session = this.sessionsScheduledNow?.find(session => session.room === this.room)
			}
			return session
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
		padding: 0 24px
		height: 56px
		box-sizing: border-box
		border-bottom: border-separator()
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
		.bunt-icon-button
			margin-left: 36px
			icon-button-style(style: clear)
			align-self: center
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

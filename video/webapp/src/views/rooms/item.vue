<template lang="pug">
.c-room(v-if="room", :class="{'standalone-chat': modules['chat.native'] && room.modules.length === 1}")
	.ui-page-header.room-info(v-if="!modules['page.markdown'] && !modules['page.landing']")
		.room-name {{ room.name }}
		.room-session(v-if="currentSession") {{ currentSession.title }}
		bunt-icon-button(v-if="$features.enabled('schedule-control')", @click="showEditSchedule = true") calendar_edit
		bunt-icon-button(@click="showRecordingsPrompt = true", :tooltip="$t('Room:recordings:tooltip')", tooltipPlacement="left", v-if="modules['call.bigbluebutton'] && hasPermission('room:bbb.recordings')") file-video-outline
	.main
		.stage(v-if="modules['livestream.native'] || modules['livestream.youtube'] || modules['call.janus']")
			.mediasource-placeholder
			reactions-overlay(v-if="modules['livestream.native'] || modules['livestream.youtube'] || modules['call.janus']")
			.stage-tool-blocker(v-if="activeStageTool !== null", @click="activeStageTool = null")
			.stage-tools(v-if="modules['livestream.native'] || modules['livestream.youtube'] || modules['call.janus']")
				.stage-tool(v-if="$features.enabled('questions-answers')", :class="{active: activeStageTool === 'qa'}", @click="activeStageTool = 'qa'") Ask a question
				reactions-bar(:expanded="true", @expand="activeStageTool = 'reaction'")
				//- reactions-bar(:expanded="activeStageTool === 'reaction'", @expand="activeStageTool = 'reaction'")
		.mediasource-placeholder(v-else-if="modules['call.bigbluebutton']")
		roulette(v-else-if="modules['networking.roulette'] && $features.enabled('roulette')", :module="modules['networking.roulette']", :room="room")
		landing-page(v-else-if="modules['page.landing']", :module="modules['page.landing']")
		markdown-page(v-else-if="modules['page.markdown']", :module="modules['page.markdown']")
		UserListPage(v-else-if="modules['page.userlist']", :module="modules['page.userlist']")
		iframe-page(v-else-if="modules['page.iframe']", :module="modules['page.iframe']")
		exhibition(v-else-if="modules['exhibition.native']", :room="room")
		chat(v-if="room.modules.length === 1 && modules['chat.native']", :room="room", :module="modules['chat.native']", mode="standalone", :key="room.id")
		.room-sidebar(v-else-if="modules['chat.native'] || modules['question']", :class="unreadTabsClasses")
			bunt-tabs(v-if="modules['question'] && modules['chat.native']", :active-tab="activeSidebarTab")
				bunt-tab(id="chat", :header="$t('Room:sidebar:tabs-header:chat')", @selected="activeSidebarTab = 'chat'")
				bunt-tab(id="questions", :header="$t('Room:sidebar:tabs-header:questions')", @selected="activeSidebarTab = 'questions'")
			chat(v-show="modules['chat.native'] && activeSidebarTab === 'chat'", :room="room", :module="modules['chat.native']", mode="compact", :key="room.id", @change="changedTabContent('chat')")
			questions(v-show="modules['question'] && activeSidebarTab === 'questions'", @change="changedTabContent('questions')")
	transition(name="prompt")
		recordings-prompt(:room="room", v-if="showRecordingsPrompt", @close="showRecordingsPrompt = false")
	edit-room-schedule(v-if="showEditSchedule", :room="room", :currentSession="currentSession", @close="showEditSchedule = false")
</template>
<script>
// TODO
// - questions without chat
// - tab activity
import {mapGetters, mapState} from 'vuex'
import EditRoomSchedule from './EditRoomSchedule'
import Chat from 'components/Chat'
import Livestream from 'components/Livestream'
import LandingPage from 'components/LandingPage'
import MarkdownPage from 'components/MarkdownPage'
import IframePage from 'components/IframePage'
import Exhibition from 'components/Exhibition'
import ReactionsBar from 'components/ReactionsBar'
import ReactionsOverlay from 'components/ReactionsOverlay'
import RecordingsPrompt from 'components/RecordingsPrompt'
import Roulette from 'components/Roulette'
import UserListPage from 'components/UserListPage'
import Questions from 'components/Questions'

export default {
	name: 'Room',
	components: { EditRoomSchedule, Chat, Exhibition, Livestream, LandingPage, MarkdownPage, IframePage, ReactionsBar, ReactionsOverlay, RecordingsPrompt, UserListPage, Roulette, Questions },
	props: {
		roomId: String
	},
	data () {
		return {
			showRecordingsPrompt: false,
			showEditSchedule: false,
			activeSidebarTab: 'chat', // chat, questions
			unreadTabs: {
				chat: false,
				questions: false,
				polls: false
			},
			activeStageTool: null // reaction, qa
		}
	},
	computed: {
		...mapGetters(['hasPermission']),
		...mapState(['connected', 'world', 'rooms']),
		...mapGetters('schedule', ['sessions', 'sessionsScheduledNow']),
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
			if (!this.$features.enabled('schedule-control')) return
			let session
			if (this.room.schedule_data) {
				session = this.sessions?.find(session => session.id === this.room.schedule_data.session)
			}
			if (!session) {
				session = this.sessionsScheduledNow?.find(session => session.room === this.room)
			}
			return session
		},
		unreadTabsClasses () {
			return Object.entries(this.unreadTabs).filter(([tab, value]) => value).map(([tab]) => `tab-${tab}-unread`)
		}
	},
	watch: {
		activeSidebarTab (tab) {
			this.unreadTabs[tab] = false
		}
	},
	mounted () {
		if (this.modules['chat.native']) {
			this.activeSidebarTab = 'chat'
		} else if (this.modules.question) {
			this.activeSidebarTab = 'questions'
		}
	},
	methods: {
		changedTabContent (tab) {
			if (tab === this.activeSidebarTab) return
			this.unreadTabs[tab] = true
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
	min-width: 0
	.main
		flex: auto
		display: flex
		min-height: 0
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
		.bunt-icon-button
			margin-left: 36px
			icon-button-style(style: clear)
			align-self: center
	.stage
		display: flex
		flex-direction: column
		min-height: 0
		flex: auto
	.mediasource-placeholder
		flex: auto
	.room-sidebar
		display: flex
		flex-direction: column
		min-height: 0
		width: var(--chatbar-width)
		flex: none
		border-left: border-separator()
		> .bunt-tabs
			tabs-style(active-color: var(--clr-primary), indicator-color: var(--clr-primary), background-color: transparent)
			margin: 0
			border-bottom: border-separator()
			.bunt-tabs-header-items
				justify-content: center
		for tab in chat questions polls
			&.tab-{tab}-unread [aria-controls=\"{tab}\"] .bunt-tab-header-item-text
				position: relative
				&::after
					content: ''
					position: absolute
					top: -2px
					right: -8px
					display: block
					height: 5px
					width: 5px
					border-radius: 50%
					background-color: $clr-danger
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
		z-index: 800
	&.standalone-chat
		.main
			flex: auto
	&:not(.standalone-chat)
		.c-chat
			min-height: 0
	+below('m')
		.main
			flex-direction: column
		.stage
			flex: none
		.room-sidebar
			width: 100%
			flex: auto
		.mediasource-placeholder
			height: 40vh
			flex: none
		&:not(.standalone-chat)
			.c-chat
				flex: auto
				width: 100vw
				min-height: 0
</style>

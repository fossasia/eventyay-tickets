<template lang="pug">
.c-room(v-if="room", :class="{'standalone-chat': modules['chat.native'] && room.modules.length === 1}")
	.stage(v-if="modules['livestream.native'] || modules['livestream.youtube'] || modules['livestream.iframe'] || modules['call.janus']")
		media-source-placeholder
		reactions-overlay(v-if="modules['livestream.native'] || modules['livestream.youtube'] || modules['livestream.iframe'] || modules['call.janus']")
		.stage-tool-blocker(v-if="activeStageTool !== null", @click="activeStageTool = null")
		.stage-tools(v-if="modules['livestream.native'] || modules['livestream.youtube'] || modules['livestream.iframe'] || modules['call.janus']")
			reactions-bar(:expanded="true", @expand="activeStageTool = 'reaction'")
			//- reactions-bar(:expanded="activeStageTool === 'reaction'", @expand="activeStageTool = 'reaction'")
	media-source-placeholder(v-else-if="modules['call.bigbluebutton'] || modules['call.zoom']")
	roulette(v-else-if="modules['networking.roulette'] && $features.enabled('roulette')", :module="modules['networking.roulette']", :room="room")
	landing-page(v-else-if="modules['page.landing']", :module="modules['page.landing']")
	markdown-page(v-else-if="modules['page.markdown']", :module="modules['page.markdown']")
	static-page(v-else-if="modules['page.static']", :module="modules['page.static']")
	UserListPage(v-else-if="modules['page.userlist']", :module="modules['page.userlist']")
	iframe-page(v-else-if="modules['page.iframe']", :module="modules['page.iframe']")
	exhibition(v-else-if="modules['exhibition.native']", :room="room")
	chat(v-if="room.modules.length === 1 && modules['chat.native']", :room="room", :module="modules['chat.native']", mode="standalone", :key="room.id")
	.room-sidebar(v-else-if="modules['chat.native'] || modules['question'] || modules['poll']", :class="unreadTabsClasses", role="complementary")
		bunt-tabs(v-if="(!!modules['question'] + !!modules['poll'] + !!modules['chat.native']) > 1 && activeSidebarTab", :active-tab="activeSidebarTab")
			bunt-tab(v-if="modules['chat.native']", id="chat", :header="$t('Room:sidebar:tabs-header:chat')", @selected="activeSidebarTab = 'chat'")
			bunt-tab(v-if="modules['question']", id="questions", :header="$t('Room:sidebar:tabs-header:questions')", @selected="activeSidebarTab = 'questions'")
			bunt-tab(v-if="modules['poll']", id="polls", :header="$t('Room:sidebar:tabs-header:polls')", @selected="activeSidebarTab = 'polls'")
		chat(v-if="modules['chat.native']", v-show="activeSidebarTab === 'chat'", :room="room", :module="modules['chat.native']", mode="compact", :key="room.id", @change="changedTabContent('chat')")
		questions(v-if="modules['question']", v-show="activeSidebarTab === 'questions'", :module="modules['question']", @change="changedTabContent('questions')")
		polls(v-if="modules['poll']", v-show="activeSidebarTab === 'polls'", :module="modules['poll']", @change="changedTabContent('polls')")
</template>
<script>
// TODO
// - questions without chat
// - tab activity
import Chat from 'components/Chat'
import LandingPage from 'components/LandingPage'
import MarkdownPage from 'components/MarkdownPage'
import StaticPage from 'components/StaticPage'
import IframePage from 'components/IframePage'
import Exhibition from 'components/Exhibition'
import ReactionsBar from 'components/ReactionsBar'
import ReactionsOverlay from 'components/ReactionsOverlay'
import Roulette from 'components/Roulette'
import UserListPage from 'components/UserListPage'
import Polls from 'components/Polls'
import Questions from 'components/Questions'
import MediaSourcePlaceholder from 'components/MediaSourcePlaceholder'

export default {
	name: 'Room',
	components: { Chat, Exhibition, LandingPage, MarkdownPage, StaticPage, IframePage, ReactionsBar, ReactionsOverlay, UserListPage, Roulette, Polls, Questions, MediaSourcePlaceholder },
	props: {
		room: Object,
		modules: Object
	},
	data () {
		return {
			activeSidebarTab: null, // chat, questions, polls
			unreadTabs: {
				chat: false,
				questions: false,
				polls: false
			},
			activeStageTool: null // reaction, qa
		}
	},
	computed: {
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
		} else if (this.modules.poll) {
			this.activeSidebarTab = 'polls'
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
	min-height: 0
	.stage
		display: flex
		flex-direction: column
		min-height: 0
		flex: auto
	.c-media-source-placeholder
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
		flex: auto
	&:not(.standalone-chat)
		.c-chat
			min-height: 0
	+below('m')
		flex-direction: column
		.stage
			flex: none
		.room-sidebar
			width: 100%
			flex: auto
		.c-media-source-placeholder
			height: var(--mobile-media-height)
			flex: none
		&:not(.standalone-chat)
			.c-chat
				flex: auto
				width: 100vw
				min-height: 0
</style>

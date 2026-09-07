<template lang="pug">
.c-room(v-if="room", :class="{'standalone-chat': modules['chat.native'] && room.modules.length === 1}")
	.room-feature-disabled(v-if="roomIsDisabled")
		.disabled-card
			i.mdi.mdi-alert-circle-outline(aria-hidden="true")
			h2 {{ $t('Feature No Longer Available') }}
			p.disabled-message {{ roomDisabledReason }}
			router-link.btn-back-dashboard(:to="{name: 'home'}") {{ $t('Back to Dashboard') }}
	.stage(v-else-if="modules['livestream.native'] || modules['livestream.youtube']")
		media-source-placeholder
		reactions-overlay(v-if="hasLivestream")
		upcoming-stream-countdown(:room="room")
		.stage-tool-blocker(v-if="activeStageTool !== null", @click="activeStageTool = null")
		.stage-tools(v-if="hasLivestream")
			reactions-bar(:expanded="true", @expand="activeStageTool = 'reaction'")
			AudioTranslationDropdown(v-if="showPluginLanguageDropdown", :key="`${room.id}-plugin`", :languages="pluginLanguages", :selected-language="selectedPluginLanguage", :label="$t('Interpretation')", @languageChanged="handlePluginLanguageChange")
	.stage(v-else-if="modules['call.janus'] || modules['call.bigbluebutton'] || modules['call.zoom'] || modules['call.jitsi'] || modules['call.loungemesh']")
		media-source-placeholder
	roulette(v-else-if="modules['networking.roulette'] && $features.enabled('roulette')", :module="modules['networking.roulette']", :room="room")
	landing-page(v-else-if="modules['page.landing']", :module="modules['page.landing']")
	markdown-page(v-else-if="modules['page.markdown']", :module="modules['page.markdown']")
	chat(v-else-if="room.modules.length === 1 && modules['chat.native']", :room="room", :module="modules['chat.native']", mode="standalone", :key="room.id")
	.room-sidebar(v-if="hasSidebar", :class="unreadTabsClasses", role="complementary")
		bunt-tabs(v-if="(!!modules['question'] + !!modules['poll'] + !!modules['chat.native']) > 1 && activeSidebarTab", :active-tab="activeSidebarTab")
			bunt-tab(v-if="modules['chat.native']", id="chat", :header="$t('Chat')", @selected="activeSidebarTab = 'chat'")
			bunt-tab(v-if="modules['question']", id="questions", :header="$t('Questions')", @selected="activeSidebarTab = 'questions'")
			bunt-tab(v-if="modules['poll']", id="polls", :header="$t('Polls')", @selected="activeSidebarTab = 'polls'")
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
import ReactionsBar from 'components/ReactionsBar'
import ReactionsOverlay from 'components/ReactionsOverlay'
import Roulette from 'components/Roulette'
import Polls from 'components/Polls'
import Questions from 'components/Questions'
import MediaSourcePlaceholder from 'components/MediaSourcePlaceholder'
import AudioTranslationDropdown from 'components/AudioTranslationDropdown'
import UpcomingStreamCountdown from 'components/UpcomingStreamCountdown'
import { normalizeAudioTranslationSource } from 'lib/validators'
import { pluginLanguageStreams, roomUsesPluginLanguageStreams } from '../../interpretation-streams'
import { hasOrganizerTraits } from 'lib/traitGrants'
import { hasEmbeddedSuite, isRoomVisibleToAttendee } from 'lib/video-providers'

export default {
	name: 'Room',
	components: {
		Chat,
		LandingPage,
		MarkdownPage,
		ReactionsBar,
		ReactionsOverlay,
		Roulette,
		Polls,
		Questions,
		MediaSourcePlaceholder,
		AudioTranslationDropdown,
		UpcomingStreamCountdown,
	},
	props: {
		room: Object,
		modules: Object
	},
	data() {
		return {
			localActiveSidebarTab: null,
			unreadTabs: {
				chat: false,
				questions: false,
				polls: false
			},
			activeStageTool: null, // reaction, qa
			pluginLanguages: [],
		}
	},
	computed: {
		activeSidebarTab: {
			get() {
				return this.$store.state.activeRoomSidebarTab || this.localActiveSidebarTab || (this.modules['chat.native'] ? 'chat' : this.modules.question ? 'questions' : this.modules.poll ? 'polls' : null)
			},
			set(tab) {
				this.localActiveSidebarTab = tab
				this.$store.commit('setActiveRoomSidebarTab', tab)
			}
		},
		roomIsDisabled() {
			if (!this.room) return false
			if (this.room.is_disabled) return true
			return !isRoomVisibleToAttendee(this.room, this.$store.state.world?.video_providers)
		},
		roomDisabledReason() {
			return this.room?.disabled_reason || this.$t('This feature is no longer available. Please contact system administrator.')
		},
		hasOrganiserPermissions() {
			if (!window.eventyay?.isOrganizerArea) return false
			if (window.eventyay?.hasOrganiserPermissions) return true
			const tokenTraits = this.$store.state.user?.traits || []
			return (
				hasOrganizerTraits(tokenTraits) ||
				this.hasPermission('world:users.list') ||
				this.hasPermission('world:update') ||
				this.hasPermission('room:update')
			)
		},
		hasEmbeddedCallSuite() {
			return hasEmbeddedSuite(this.modules)
		},
		hasSidebar() {
			if (this.roomIsDisabled) return false
			// Video conference suites (BigBlueButton, Jitsi, Zoom) have their own native in-frame
			// options for chats, polls, questions, etc.; do not show platform native sidebar for them.
			// Janus WebRTC uses native platform chat and displays the sidebar when chat.native is attached.
			if (this.hasEmbeddedCallSuite) return false
			if (this.room?.modules?.length === 1 && this.modules['chat.native']) return false
			if (this.$store.state.roomSidebarCollapsedByRoom?.[this.room?.id]) return false
			return Boolean(
				this.modules['chat.native'] ||
				this.modules['question'] ||
				this.modules['poll']
			)
		},
		currentInterpretation() {
			if (!this.room?.id) return null
			return this.$store.state.interpretationStreamsByRoom?.[this.room.id] || this.$store.state.youtubeTranslationsByRoom?.[this.room.id] || null
		},
		showPluginLanguageDropdown() {
			return roomUsesPluginLanguageStreams(this.room) && this.pluginLanguages.length > 0
		},
		selectedPluginLanguage() {
			return this.getLanguageForTranslation(this.currentInterpretation, this.pluginLanguages) || 'Original'
		},
		usesStreamPolling() {
			return Boolean(
				this.modules['livestream.native'] ||
				this.modules['livestream.youtube']
			)
		},
		unreadTabsClasses() {
			return Object.entries(this.unreadTabs).filter(([tab, value]) => value).map(([tab]) => `tab-${tab}-unread`)
		},
		hasLivestream() {
			return Boolean(
				this.modules['livestream.native'] ||
				this.modules['livestream.youtube']
			)
		}
	},
	watch: {
		activeSidebarTab(tab) {
			this.unreadTabs[tab] = false
		},
		room: {
			handler() {
				this.initializeLanguages()
				this.checkDirectAccess()
			},
			immediate: true
		},
		rooms: {
			handler() {
				this.checkDirectAccess()
			},
			immediate: true
		},
		'room.currentStream': {
			handler: 'initializeLanguages'
		},
		'room.interpretation_language_streams': {
			handler: 'initializeLanguages'
		},
		'room.interpretation_use_plugin_streams': {
			handler: 'initializeLanguages'
		},
		'room.id'(roomId) {
			this.$store.dispatch('stopStreamPolling')
			if (roomId && this.usesStreamPolling) {
				this.$store.dispatch('startStreamPolling', roomId)
			}
		},
	},
	async created() {
		if (this.modules['chat.native']) {
			this.activeSidebarTab = 'chat'
		} else if (this.modules.question) {
			this.activeSidebarTab = 'questions'
		} else if (this.modules.poll) {
			this.activeSidebarTab = 'polls'
		}
		if (this.room?.id && this.usesStreamPolling) {
			await this.$nextTick()
			this.$store.dispatch('startStreamPolling', this.room.id)
		}
	},
	mounted() {
		this.checkDirectAccess()
	},
	beforeUnmount() {
		this.$store.dispatch('stopStreamPolling')
	},
	methods: {
		checkDirectAccess() {
			if (!this.rooms || this.rooms.length === 0) return
			if (!this.hasOrganiserPermissions) {
				const roomId = this.roomId || this.$route.params.roomId
				if (roomId && (!this.room || this.roomIsDisabled)) {
					this.$router.replace({ name: 'about' })
				}
			}
		},
		changedTabContent(tab) {
			if (tab === this.activeSidebarTab) return
			this.unreadTabs[tab] = true
		},
		handlePluginLanguageChange(translationConfig) {
			this.updateActiveTranslation(translationConfig)
		},
		updateActiveTranslation(translationConfig) {
			this.$store.commit('updateInterpretationAudio', {
				roomId: this.room?.id,
				interpretation: translationConfig
			})
		},
		initializeLanguages() {
			this.pluginLanguages = roomUsesPluginLanguageStreams(this.room)
				? pluginLanguageStreams(this.room)
				: []
			this.clearStaleTranslation()
		},
		getLanguageForTranslation(translationConfig, languages) {
			if (!translationConfig?.url || !languages?.length) return 'Original'
			const matchingLanguage = languages.find(entry => (
				entry.language !== 'Original' &&
				normalizeAudioTranslationSource(entry.url || entry.youtube_id) === translationConfig.url &&
				!!entry.use_video === !!translationConfig.useVideo
			))
			return matchingLanguage?.language || null
		},
		clearStaleTranslation() {
			if (!this.room?.id || !this.currentInterpretation) return
			const matchesPlugin = this.getLanguageForTranslation(this.currentInterpretation, this.pluginLanguages)
			if (!this.showPluginLanguageDropdown || !matchesPlugin) {
				this.$store.commit('updateInterpretationAudio', {
					roomId: this.room.id,
					interpretation: null
				})
			}
		}
	}
}
</script>
<style lang="stylus">
.c-room
	flex: auto
	display: flex
	min-height: 0
	min-width: 0
	max-width: 100%
	overflow: hidden
	.stage
		display: flex
		flex-direction: column
		min-height: 0
		min-width: 0
		max-width: 100%
		flex: auto
		overflow: hidden
		position: relative
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
			&.tab-{tab}-unread [aria-controls="{tab}"] .bunt-tab-header-item-text
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
		min-height: 40px
		justify-content: flex-end
		align-items: center
		flex-wrap: wrap
		gap: 6px
		padding: 4px 8px
		user-select: none
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
		+below('m')
			justify-content: space-between
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
	.room-feature-disabled
		display: flex
		flex-direction: column
		align-items: center
		justify-content: center
		width: 100%
		height: 100%
		min-height: 60vh
		padding: 32px
		background-color: $clr-grey-50
		flex: auto

		.disabled-card
			max-width: 520px
			text-align: center
			padding: 40px 32px
			background-color: $clr-white
			border: 1px solid $clr-grey-200
			border-radius: 8px
			box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05)

			i.mdi
				font-size: 56px
				color: #d9534f
				margin-bottom: 16px
				display: block

			h2
				font-size: 22px
				font-weight: 600
				color: $clr-grey-900
				margin: 0 0 12px

			.disabled-message
				font-size: 15px
				line-height: 1.5
				color: $clr-grey-700
				margin: 0 0 24px

			.btn-back-dashboard
				display: inline-block
				padding: 9px 22px
				background-color: #337ab7
				color: #ffffff
				border-radius: 4px
				font-size: 14px
				font-weight: 500
				text-decoration: none
				transition: background-color 0.15s ease
				&:hover
					background-color: #286090
					text-decoration: none
</style>

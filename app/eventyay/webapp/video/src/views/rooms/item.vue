<template lang="pug">
.c-room(v-if="room", :class="{'standalone-chat': modules['chat.native'] && room.modules.length === 1}")
	.stage(v-if="modules['livestream.native'] || modules['livestream.youtube'] || modules['call.janus']", style="container-type: inline-size;")
		media-source-placeholder
		LiveCaptions(v-if="ccEnabled", :ws-url="selectedCcWsUrl")
		reactions-overlay(v-if="hasLivestream")
		upcoming-stream-countdown(:room="room")
		.stage-tool-blocker(v-if="activeStageTool !== null", @click="activeStageTool = null")
		.stage-tools(v-if="hasLivestream")
			reactions-bar(:expanded="true", @expand="activeStageTool = 'reaction'")
			.cc-controls(v-if="showPluginLanguageDropdown", style="display: flex; align-items: center;")
				button.stage-tool.cc-toggle(:class="{active: ccEnabled}", @click="toggleCc", style="margin-right: 8px;", :title="$t('Toggle Captions')")
					i.mdi.mdi-closed-caption
				AudioTranslationDropdown(v-if="ccEnabled", :key="`${room.id}-cc`", :languages="pluginLanguages", :selected-language="selectedCcLanguage", :label="$t('Caption Language')", @languageChanged="handleCcLanguageChange", icon="mdi-cog")
				AudioTranslationDropdown(v-if="showPluginLanguageDropdown", :key="`${room.id}-plugin`", :languages="pluginLanguages", :selected-language="selectedPluginLanguage", :label="$t('Interpretation')", @languageChanged="handlePluginLanguageChange", icon="mdi-headphones")
				button.stage-tool.ai-toggle(:class="{active: isAiTtsEnabled}", @click="isAiTtsEnabled = !isAiTtsEnabled", :title="$t('Enable AI TTS')", style="margin-right: 8px;")
					i.mdi.mdi-robot
	media-source-placeholder(v-else-if="modules['call.bigbluebutton'] || modules['call.zoom'] || modules['call.jitsi']")
	roulette(v-else-if="modules['networking.roulette'] && $features.enabled('roulette')", :module="modules['networking.roulette']", :room="room")
	landing-page(v-else-if="modules['page.landing']", :module="modules['page.landing']")
	markdown-page(v-else-if="modules['page.markdown']", :module="modules['page.markdown']")
	chat(v-if="room.modules.length === 1 && modules['chat.native']", :room="room", :module="modules['chat.native']", mode="standalone", :key="room.id")
	.room-sidebar(v-else-if="modules['chat.native'] || modules['question'] || modules['poll']", :class="unreadTabsClasses", role="complementary")
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
import LiveCaptions from 'components/LiveCaptions'
import UpcomingStreamCountdown from 'components/UpcomingStreamCountdown'
import api from 'lib/api'
import { normalizeAudioTranslationSource } from 'lib/validators'
import { pluginLanguageStreams, roomUsesPluginLanguageStreams } from '../../interpretation-streams'
import { interpretationApiUrl, interpretationAuthHeaders } from 'lib/interpretation-api'

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
		LiveCaptions,
		UpcomingStreamCountdown,
	},
	props: {
		room: Object,
		modules: Object
	},
	data() {
		return {
			activeSidebarTab: null, // chat, questions, polls
			unreadTabs: {
				chat: false,
				questions: false,
				polls: false
			},
			activeStageTool: null, // reaction, qa
			pluginLanguages: [],
			ccEnabled: false,
			isManualCCOverride: false,
			selectedCcLanguage: 'Original',
			listenerToken: null,
			isAiTtsEnabled: false,
			pollingInterval: null,
			activeTranslationConfig: null,
		}
	},
	computed: {
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
		selectedCcWsUrl() {
			if (!this.ccEnabled) return null
			const lang = this.pluginLanguages.find(l => l.language === this.selectedCcLanguage)
			if (lang && lang.caption_ws_url && this.listenerToken) {
				return `${lang.caption_ws_url}?token=${this.listenerToken}`
			}
			return null
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
		},

	},
	watch: {
		activeSidebarTab(tab) {
			this.unreadTabs[tab] = false
		},
		room: {
			handler: 'initializeLanguages',
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
		isAiTtsEnabled() {
			this.recomputeInterpretationAudio();
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
		if (this.room?.id) {
			this.fetchListenerToken()
		}
	},
	beforeUnmount() {
		this.$store.dispatch('stopStreamPolling')
	},
	methods: {
		async fetchListenerToken() {
			if (!this.room?.id) return;
			// Use interpretationApiUrl + interpretationAuthHeaders so X-CSRFToken is included
			const url = interpretationApiUrl(this.$store, this.room.id, 'listener-token/');
			const headers = await interpretationAuthHeaders(true);
			try {
				const response = await fetch(url, { method: 'POST', headers, credentials: 'include' });
				if (response.ok) {
					const data = await response.json();
					if (data && data.token) {
						this.listenerToken = data.token;
					}
				} else {
					console.error('listener-token failed:', response.status);
				}
			} catch (err) {
				console.error('Failed to fetch listener token', err);
			}
		},
		changedTabContent(tab) {
			if (tab === this.activeSidebarTab) return
			this.unreadTabs[tab] = true
		},
		handlePluginLanguageChange(translationConfig) {
			this.updateActiveTranslation(translationConfig)
			if (!this.isManualCCOverride && this.ccEnabled) {
				this.selectedCcLanguage = this.getLanguageForTranslation(translationConfig, this.pluginLanguages) || 'Original'
			}
		},
		handleCcLanguageChange(translationConfig) {
			this.isManualCCOverride = true
			this.selectedCcLanguage = this.getLanguageForTranslation(translationConfig, this.pluginLanguages) || 'Original'
		},
		toggleCc() {
			this.ccEnabled = !this.ccEnabled
			if (this.ccEnabled && !this.isManualCCOverride) {
				this.selectedCcLanguage = this.selectedPluginLanguage
			}
		},
		updateActiveTranslation(translationConfig) {
			this.activeTranslationConfig = translationConfig;
			this.recomputeInterpretationAudio();
		},
		recomputeInterpretationAudio() {
			let finalConfig = null;
			if (this.selectedPluginLanguage !== 'Original') {
				finalConfig = this.activeTranslationConfig;
			}
			this.$store.commit('updateInterpretationAudio', {
				roomId: this.room?.id,
				interpretation: finalConfig
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
	.stage
		display: flex
		flex-direction: column
		min-height: 0
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
</style>

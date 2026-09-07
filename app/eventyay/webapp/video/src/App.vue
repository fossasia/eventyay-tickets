<template lang="pug">
.v-app(:key="`${userLocale}-${userTimezone}`", :class="{'has-background-room': backgroundRoom, 'override-sidebar-collapse': overrideSidebarCollapse}", :style="[browserhackStyle, mediaConstraintsStyle]")
	.fatal-connection-error(v-if="fatalConnectionError")
		template(v-if="fatalConnectionError.code === 'world.unknown_world'")
			.mdi.mdi-help-circle
			h1 {{ $t('Event not found') }}
		template(v-else-if="fatalConnectionError.code === 'connection.replaced'")
			.mdi.mdi-alert-octagon
			h1 {{ $t('You opened this event on a new device or tab.') }}
			bunt-button(@click="reload") {{ $t('Continue (disconnect other device)') }}
		template(v-else-if="['auth.denied', 'auth.invalid_token', 'auth.missing_token', 'auth.expired_token'].includes(fatalConnectionError.code)")
			.mdi.mdi-alert-octagon
			h1 {{ fatalAuthHeadline }}
				br
				small {{ fatalAuthText }}
			bunt-button(v-if="fatalConnectionError.code != 'auth.missing_token'", @click="clearTokenAndReload") {{ fatalAuthAction }}
		template(v-else)
			h1 {{ $t('Connection refused') }}
		p.code {{ $t('error code:') }} {{ fatalConnectionError.code }}
	template(v-else-if="world")
		// AppBar stays fixed; only main content shifts
		app-bar(:show-actions="true", :show-user="true", @toggle-sidebar="toggleSidebar")
		transition(name="backdrop")
			.sidebar-backdrop(v-if="showMobileSidebar && $mq.below.m", @click="showMobileSidebar = false")
		.app-content(:class="{'sidebar-collapsed': sidebarCollapsed, 'is-admin-view': isAdminRoute}", role="main", tabindex="-1")
			// router-view no longer carries role=main; main landmark is the scroll container
			router-view(:key="$route.fullPath")
			//- defining keys like this keeps the playing dom element alive for uninterupted transitions
			//- Single MediaSource for room streaming (persists across navigation to prevent stream restart)
			media-source(v-if="streamingRoom && user.profile.greeted && !hasFatalError(streamingRoom)", ref="mediaSource", :room="streamingRoom", :background="isStreamInBackground", :key="streamingRoom.id", :role="isStreamInBackground ? null : 'main'", @close="backgroundRoom = null")
			media-source(v-if="call", ref="channelCallSource", :call="call", :background="call.channel !== $route.params.channelId", :key="call.id", @close="$store.dispatch('chat/leaveCall')")
			#media-source-iframes
			notifications(:hasBackgroundMedia="isStreamInBackground")
			.disconnected-warning(v-if="!connected") {{ $t('Connection lost! Trying to reconnect…') }}
			transition(name="prompt")
				greeting-prompt(v-if="!user.profile.greeted")
		organiser-sidebar(v-if="isAdminRoute", :collapsed="sidebarCollapsed", :show-mobile="showMobileSidebar", @close="showMobileSidebar = false")
		rooms-sidebar(v-else, :collapsed="sidebarCollapsed", :show-mobile="showMobileSidebar", @close="showMobileSidebar = false")
	.connecting(v-else-if="!currentFatalError")
		bunt-progress-circular(size="huge")
		.details(v-if="socketCloseCode == 1006") {{ $t("Connection failed. We'll retry, but if this error occurs repeatedly, the connection might be blocked by a firewall in your network or by a VPN on your device.") }}
		.details(v-if="socketCloseCode") {{ $t('Error code') }}: {{ socketCloseCode }}
	.fatal-error(v-if="currentFatalError") {{ currentFatalError.message || currentFatalError.code }}
</template>
<script>
import { mapState } from 'vuex'
import { computed, reactive } from 'vue'
import moment from 'lib/timetravelMoment'
import { inferRoomType, inferType } from 'lib/room-types'
import { loadStarredSharingPreference, updateStarredSharingPreference } from '@schedule/utils'
import AppBar from 'components/AppBar'
import RoomsSidebar from 'components/RoomsSidebar'
import OrganiserSidebar from 'components/OrganiserSidebar'
import MediaSource from 'components/MediaSource'
import Notifications from 'components/notifications'
import GreetingPrompt from 'components/profile/GreetingPrompt'

const mediaModules = ['livestream.native', 'livestream.youtube', 'call.bigbluebutton', 'call.janus', 'call.zoom', 'call.jitsi']
const stageToolModules = ['livestream.native', 'livestream.youtube', 'call.janus']
const chatbarModules = ['chat.native', 'question', 'poll']

export default {
	components: { AppBar, RoomsSidebar, OrganiserSidebar, MediaSource, GreetingPrompt, Notifications },
	provide() {
		return {
			eventUrl: window.eventyay?.eventUrl || '',
			scheduleData: reactive({
				schedule: computed(() => this.$store.state.schedule?.schedule),
				sessions: computed(() => this.$store.getters['schedule/sessions']),
				rooms: computed(() => this.$store.getters['schedule/rooms']),
				days: computed(() => this.$store.getters['schedule/days']),
				favs: computed(() => this.$store.getters['schedule/favs'] || []),
				now: computed(() => this.$store.state.now),
				timezone: computed(() => this.$store.state.userTimezone || moment.tz.guess()),
				hasAmPm: new Intl.DateTimeFormat(undefined, {hour: 'numeric'}).resolvedOptions().hour12,
				scheduleLoaded: computed(() => this.$store.state.schedule?.scheduleLoaded),
				errorLoading: computed(() => this.$store.state.schedule?.errorLoading),
				speakersLookup: computed(() => this.$store.getters['schedule/speakersLookup']),
				sessionsBySpeaker: computed(() => this.$store.getters['schedule/sessionsBySpeaker']),
			}),
			scheduleFav: (id) => this.$store.dispatch('schedule/fav', id),
			scheduleUnfav: (id) => this.$store.dispatch('schedule/unfav', id),
			scheduleExporters: computed(() => this.$store.getters['schedule/exporters'] || []),
			scheduleMetaData: computed(() => this.$store.getters['schedule/scheduleMetaData'] || {}),
			linkTarget: '_blank',
			generateSessionLinkUrl: ({session}) => {
				if (session.url) return session.url
				return this.$router.resolve(this.getSessionRoute(session)).href
			},
			onSessionLinkClick: async (event, session) => {
				if (!session.url) {
					event.preventDefault()
					await this.$router.push(this.getSessionRoute(session))
				}
			},
			generateSpeakerLinkUrl: ({speaker} = {}) => {
				if (!speaker?.code) return ''
				return this.$router.resolve({name: 'schedule:speaker', params: {speakerId: speaker.code}}).href
			},
			onSpeakerLinkClick: async (event, speaker) => {
				event.preventDefault()
				if (!speaker?.code) return
				await this.$router.push({name: 'schedule:speaker', params: {speakerId: speaker.code}})
			},
			showJoinRoom: true,
			getJoinRoomLink: (session) => {
				if ((!session?.stream_url && !session?.has_video_room) || !session?.room) return ''
				const room = session.room
				const rawId = typeof room === 'object' ? (room.pretalx_id ?? room.id) : room
				const worldRoom = (this.rooms || []).find(r =>
					String(r.id) === String(typeof room === 'object' ? room.id : room) ||
					(r.pretalx_id != null && String(r.pretalx_id) === String(rawId))
				)
				if (!worldRoom?.id) return ''
				return this.$router.resolve({name: 'room', params: {roomId: worldRoom.id}}).href
			},
			generateStarrerLinkUrl: (user) => {
				if (!user?.url || !user?.code) return ''
				return this.$router.resolve({name: 'schedule:public-stars', params: {userCode: user.code}}).href
			},
			onStarrerLinkClick: async (event, user) => {
				if (user?.code && user?.url) {
					event.preventDefault()
					await this.$router.push({name: 'schedule:public-stars', params: {userCode: user.code}})
				}
			},
			scheduleUserLoggedIn: computed(() => !!this.$store.state.user),
			loadStarredSharingPreference: () => this.loadStarredSharingPreference(),
			updateStarredSharingPreference: (value) => this.updateStarredSharingPreference(value),
			onSaveTimezone: (timezone) => this.$store.dispatch('updateUserTimezone', timezone),
			translationMessages: window.eventyay?.translationMessages || {}
		}
	},
	data() {
		return {
			backgroundRoom: null,
			previousRouteName: null,
			sidebarCollapsed: typeof window !== 'undefined' ? localStorage.getItem('sidebarCollapsed') === '1' : false,
			showMobileSidebar: false,
			windowHeight: null,
			shareStarredSessions: !!window.eventyay?.showPublicly,
		}
	},
	computed: {
		...mapState(['fatalConnectionError', 'fatalError', 'connected', 'socketCloseCode', 'world', 'rooms', 'user', 'mediaSourcePlaceholderRect', 'userLocale', 'userTimezone', 'roomFatalErrors']),
		...mapState('notifications', ['askingPermission']),
		...mapState('chat', ['call']),
		currentFatalError() {
			if (this.room && this.roomFatalErrors?.[this.room.id]) {
				return this.roomFatalErrors[this.room.id]
			}
			if (!this.room && this.$route?.name && this.roomFatalErrors) {
				const backgroundFatal = this.backgroundRoom && this.roomFatalErrors[this.backgroundRoom.id]
				if (backgroundFatal) return backgroundFatal
			}
			return this.fatalError?.roomId ? (this.room && this.fatalError.roomId === this.room.id ? this.fatalError : null) : this.fatalError
		},
		fatalAuthHeadline() {
			return {
				'auth.denied': this.$t('Access denied'),
				'auth.invalid_token': this.$t('Your login is invalid'),
				'auth.missing_token': this.$t('You are not logged in'),
				'auth.expired_token': this.$t('Your login has expired'),
			}[this.fatalConnectionError?.code] || this.$t('Authentication failed')
		},
		fatalAuthText() {
			return {
				'auth.denied': this.$t('You do not have permission to join this event.'),
				'auth.invalid_token': this.$t('Please log in again to continue.'),
				'auth.missing_token': this.$t('Log in to join this event.'),
				'auth.expired_token': this.$t('Please log in again to continue.'),
			}[this.fatalConnectionError?.code] || ''
		},
		fatalAuthAction() {
			return this.$t('Try again')
		},
		room() {
			const routeName = this.$route?.name
			if (!routeName) return
			const rooms = this.rooms || []
			if (routeName === 'about') {
				return rooms.find(room => room && room.modules && room.modules.some(m => m.type === 'page.landing'))
			}
			if (typeof routeName === 'string' && (routeName.startsWith('admin') || routeName === 'organizer')) {
				return null
			}
			const wantedId = this.$route.params?.roomId ? String(this.$route.params.roomId) : null
			if (wantedId) {
				return rooms.find(room => String(room.id) === wantedId || (room.pretalx_id != null && String(room.pretalx_id) === wantedId)) || null
			}
			return null
		},
		isAdminRoute() {
			const route = this.$route
			return this.isOrganizerRouteName(route?.name) ||
				route?.matched?.some(match => this.isOrganizerRouteName(match.name))
		},
		// TODO since this is used EVERYWHERE, use provide/inject?
		modules() {
			return this.room?.modules?.reduce((acc, module) => {
				acc[module.type] = module
				return acc
			}, {}) || {}
		},
		roomHasMedia() {
			if (this.hasFatalError(this.room)) return false
			return this.room?.modules.some(module => mediaModules.includes(module.type))
		},
		// Single source of truth for which room should be streaming
		// Returns the current room if it has media, otherwise the background room
		streamingRoom() {
			if (this.roomHasMedia) return this.room
			if (this.isAdminRoute) return null
			if (this.backgroundRoom && !this.hasFatalError(this.backgroundRoom)) return this.backgroundRoom
			return null
		},
		// Determines if the streaming room should be shown in background (mini-window) mode
		// True when we have a background room that's different from the current room
		isStreamInBackground() {
			if (this.isAdminRoute) return false
			return this.backgroundRoom && this.room !== this.backgroundRoom
		},
		stageStreamCollapsed() {
			if (this.$mq.above.m) return false
			return this.mediaSourceRefs.media?.$refs.livestream ? !this.mediaSourceRefs.media.$refs.livestream.playing : false
		},
		// force open sidebar on medium screens on home page (with no media) so certain people can find the menu
		overrideSidebarCollapse() {
			return this.$mq.below.l &&
				this.$mq.above.m &&
				this.$route.name === 'about' &&
				!this.roomHasMedia
		},
		// safari cleverly includes the address bar cleverly in 100vh
		mediaConstraintsStyle() {
			const hasStageTools = this.room?.modules.some(module => stageToolModules.includes(module.type))
			const hasChatbar = (
				(this.room?.modules.length > 1 && this.room?.modules.some(module => chatbarModules.includes(module.type))) ||
				(this.call && this.call.channel === this.$route.params.channelId)
			)
			const style = {
				'--chatbar-width': hasChatbar ? '380px' : '0px',
				'--mobile-media-height': this.stageStreamCollapsed ? '56px' : hasChatbar ? 'min(56.25vw, 40vh)' : (hasStageTools ? 'calc(var(--vh100) - 48px - 2 * 56px)' : 'calc(var(--vh100) - 48px - 56px)'),
				'--has-stagetools': hasStageTools ? '1' : '0'
			}
			if (this.mediaSourcePlaceholderRect) {
				Object.assign(style, {
					'--mediasource-placeholder-top': this.mediaSourcePlaceholderRect.top + 'px',
					'--mediasource-placeholder-left': this.mediaSourcePlaceholderRect.left + 'px',
					'--mediasource-placeholder-height': this.mediaSourcePlaceholderRect.height + 'px',
					'--mediasource-placeholder-width': this.mediaSourcePlaceholderRect.width + 'px'
				})
			}
			return style
		},
		browserhackStyle() {
			return {
				'--vh100': this.windowHeight + 'px',
				'--vh': this.windowHeight && (this.windowHeight / 100) + 'px'
			}
		},
		// Map the named refs used for media sources into a single object so
		// other computed properties can safely reference them.
		mediaSourceRefs() {
			return {
				media: this.$refs.mediaSource,
				channel: this.$refs.channelCallSource
			}
		}
	},
	created() {
		this.previousRouteName = this.$route?.name ?? null
	},
	watch: {
		'$route': {
			handler(to, from) {
				this.previousRouteName = from?.name ?? null
				if (this.isOrganizerRouteName(to?.name) || to?.matched?.some(match => this.isOrganizerRouteName(match.name))) {
					this.backgroundRoom = null
				}
			},
			flush: 'sync'
		},
		world: 'worldChange',
		rooms: 'roomListChange',
		room: 'roomChange',
		call: 'callChange',
		roomFatalErrors: {
			handler() {
				if (this.backgroundRoom && this.hasFatalError(this.backgroundRoom)) {
					this.backgroundRoom = null
				}
			},
			deep: true
		},
		stageStreamCollapsed: {
			handler() {
				this.$store.commit('updateStageStreamCollapsed', this.stageStreamCollapsed)
			},
			immediate: true
		}
	},
	mounted() {
		this.windowHeight = window.innerHeight
		window.addEventListener('resize', this.onResize)
		window.addEventListener('focus', this.onFocus, true)
		window.addEventListener('pointerdown', this.onGlobalPointerDown, true)
		window.addEventListener('keydown', this.onKeydown, true)
	},
	beforeUnmount() {
		window.removeEventListener('resize', this.onResize)
		window.removeEventListener('focus', this.onFocus)
		window.removeEventListener('pointerdown', this.onGlobalPointerDown, true)
		window.removeEventListener('keydown', this.onKeydown, true)
	},
	methods: {
		async loadStarredSharingPreference() {
			if (!this.$store.state.user) {
				this.shareStarredSessions = false
				return false
			}
			const eventUrl = window.eventyay?.eventUrl || ''
			const enabled = await loadStarredSharingPreference(eventUrl)
			this.shareStarredSessions = enabled
			return enabled
		},
		async updateStarredSharingPreference(value) {
			if (!this.$store.state.user) return false
			const eventUrl = window.eventyay?.eventUrl || ''
			const previous = this.shareStarredSessions
			this.shareStarredSessions = !!value
			try {
				const enabled = await updateStarredSharingPreference(eventUrl, this.shareStarredSessions)
				this.shareStarredSessions = enabled
				return enabled
			} catch {
				this.shareStarredSessions = previous
				throw new Error('sharing preference update failed')
			}
		},
		getSessionRoute(session) {
			if (session.room?.modules) {
				return {name: 'room', params: {roomId: session.room.id}}
			}
			return {name: 'schedule:talk', params: {talkId: session.id}}
		},
		hasFatalError(room) {
			return !!(room && this.roomFatalErrors?.[room.id])
		},
		onKeydown(e) {
			if ((e.key === 'Escape' || e.key === 'Esc') && this.showMobileSidebar) {
				this.showMobileSidebar = false
				// Prevent the Escape from triggering other handlers if we handled it
				e.stopPropagation()
			}
		},
		onResize() {
			// Only track height for CSS vars; no breakpoint-based sidebar behavior
			this.windowHeight = window.innerHeight
		},
		onFocus() {
			this.$store.dispatch('notifications/clearDesktopNotifications')
		},
		toggleSidebar() {
			if (this.$mq?.below?.m) {
				this.showMobileSidebar = !this.showMobileSidebar
			} else {
				this.sidebarCollapsed = !this.sidebarCollapsed
				try {
					localStorage.setItem('sidebarCollapsed', this.sidebarCollapsed ? '1' : '')
				} catch (e) {
					// ignore
				}
			}
		},
		onGlobalPointerDown(event) {
			if (!this.showMobileSidebar || this.$mq?.above?.m) return
			const sidebarEl = document.querySelector('.c-rooms-sidebar') || document.querySelector('.c-organiser-sidebar')
			const hamburgerEl = document.querySelector('.c-app-bar .navbar-toggle-sidebar')
			if (sidebarEl?.contains(event.target) || hamburgerEl?.contains(event.target)) return
			this.showMobileSidebar = false
		},
		clearTokenAndReload() {
			try {
				localStorage.removeItem('token')
				sessionStorage.removeItem('video_auth_mode')
			} catch (e) {}
			location.reload()
		},
		reload() {
			location.reload()
		},
		isOrganizerRouteName(name) {
			return typeof name === 'string' && (name.startsWith('admin') || name === 'organizer' || name === 'room:manage')
		},
		worldChange() {
			// initial connect
			document.title = this.world.title
		},
		callChange() {
			if (this.call) {
				// When a DM call starts, all other background media stops
				this.backgroundRoom = null
			}
		},
		roomChange(newRoom, oldRoom) {
			// HACK find out why this is triggered often
			if (newRoom === oldRoom) return
			// TODO non-room urls
			let title = this.world.title
			if (newRoom?.name) {
				title += ` | ${newRoom.name}`
			}
			document.title = title
			if (this.hasFatalError(newRoom)) {
				this.$store.dispatch('changeRoom', newRoom)
				this.backgroundRoom = null
				return
			}
			this.$store.dispatch('changeRoom', newRoom)
			const isExclusive = module => module.type === 'call.bigbluebutton' || module.type === 'call.zoom' || module.type === 'call.jitsi'
			if (!this.$mq.above.m) return // no background rooms for mobile
			if (this.call) return // When a DM call is running, we never want background media
			if (this.isAdminRoute || this.isOrganizerRouteName(this.previousRouteName)) {
				this.backgroundRoom = null
				return
			}
			const newRoomHasMedia = newRoom && newRoom.modules && newRoom.modules.some(module => mediaModules.includes(module.type))
			// We treat "undefined / not callable" as true to avoid race conditions.
			let primaryWasPlaying = true
			const mediaRef = this.mediaSourceRefs.media
			if (typeof mediaRef?.isPlaying === 'function') {
				const result = mediaRef.isPlaying()
				if (result === false) primaryWasPlaying = false
			}
			if (oldRoom &&
				this.rooms.includes(oldRoom) &&
				!this.backgroundRoom &&
				oldRoom.modules.some(module => mediaModules.includes(module.type)) &&
				!this.hasFatalError(oldRoom) &&
				primaryWasPlaying &&
				// don't background bbb room when switching to new bbb room
				!(newRoom?.modules.some(isExclusive) && oldRoom?.modules.some(isExclusive)) &&
				!newRoomHasMedia
			) {
				this.backgroundRoom = oldRoom
			} else if (newRoomHasMedia) {
				this.backgroundRoom = null
			}
			// returning to room currently playing in background should maximize again
			if (this.backgroundRoom && (
				newRoom === this.backgroundRoom ||
				// close background bbb room if entering new bbb room
				(newRoom?.modules.some(isExclusive) && this.backgroundRoom.modules.some(isExclusive))
			)) {
				this.backgroundRoom = null
			}
		},
		roomListChange() {
			if (this.room && !this.rooms.includes(this.room)) {
				this.$router.push('/').catch(() => {})
			}
			if (!this.backgroundRoom && !this.rooms.includes(this.backgroundRoom)) {
				this.backgroundRoom = null
			}
		}
	}
}
</script>
<style lang="stylus">
.v-app
	flex: auto
	min-height: 0
	display: flex
	flex-direction: column
	--sidebar-width: 250px
	--pretalx-clr-primary: var(--clr-primary)
	.app-content
		flex: 1 1 auto
		min-height: 0
		height: calc(100vh - 50px)
		display: flex
		flex-direction: column
		position: relative
		padding-top: 50px
		z-index: 1
		transition: padding-left 0.2s cubic-bezier(0.4, 0, 0.2, 1)
		+above('m')
			padding-left: 250px !important
			&.sidebar-collapsed
				padding-left: 45px !important
		+below('m')
			padding-left: 0 !important
		> .c-schedule-view, > .c-speaker-detail, > .c-speakers-list, > .c-talk-detail, > .c-public-stars
			flex: 1 1 auto
			min-height: 0
			min-width: 0
			width: 100%
			box-sizing: border-box
	.sidebar-backdrop
		position: fixed
		top: 50px
		left: 0
		right: 0
		bottom: 0
		background-color: rgba(0, 0, 0, 0.4)
		z-index: 110
		+above('m')
			display: none !important
		&.backdrop-enter-active, &.backdrop-leave-active
			transition: opacity .2s
		&.backdrop-enter-from, &.backdrop-leave-to
			opacity: 0
	.main-content
		grid-area: main
		display: flex
		flex-direction: column
		min-height: var(--vh100)
		min-width: 0
	.c-app-bar
		grid-area: app-bar
	.c-rooms-sidebar
		grid-area: rooms-sidebar
	.c-room-header
		grid-area: main
		height: 100vh
	> .bunt-progress-circular
		position: fixed
		top: 50%
		left: 50%
		transform: translate(-50%, -50%)
	.disconnected-warning, .fatal-error
		position: fixed
		top: 48px
		left: calc(50% - 240px)
		width: 480px
		background-color: $clr-danger
		color: $clr-primary-text-dark
		padding: 16px
		box-sizing: border-box
		text-align: center
		font-weight: 600
		font-size: 20px
		border-radius: 0 0 4px 4px
		z-index: 2000
	.connecting
		display: flex
		height: var(--vh100)
		width: 100vw
		flex-direction: column
		justify-content: center
		align-items: center
		.details
			text-align: center
			max-width: 400px
			margin-top: 30px
			color: var(--clr-text-secondary)
	.fatal-connection-error
		position: fixed
		top: 0
		left: 0
		right: 0
		bottom: 0
		display: flex
		flex-direction: column
		justify-content: center
		align-items: center
		.mdi
			font-size: 10vw
			color: $clr-danger
		h1
			font-size: 3vw
			text-align: center
		.code
			font-family: monospace
		.bunt-button
			themed-button-primary('large')
	.native-permission-blocker
		position: fixed
		top: 48px
		left: 0
		width: 100vw
		height: calc(var(--vh100) - 48px)
		z-index: 2000
		background-color: $clr-secondary-text-light
	#media-source-iframes
		position: absolute
		width: 0
		height: 0

@media print
	@page
		size: A4 landscape
		margin: 5mm
	.v-app
		display: block !important
		overflow: visible !important
		height: auto !important
		.c-app-bar
			display: none !important
		.c-rooms-sidebar
			display: none !important
		.sidebar-backdrop
			display: none !important
		.disconnected-warning
			display: none !important
		.native-permission-blocker
			display: none !important
		.app-content
			padding-top: 0 !important
			height: auto !important
			overflow: visible !important
			display: block !important
		.pretalx-schedule
			height: auto !important
			overflow: visible !important
			&:fullscreen
				padding: 0
			.days
				position: static !important
			.error-messages
				display: none
		.pretalx-modal
			display: none !important
		.c-linear-schedule-session, .break
			break-inside: avoid
			page-break-inside: avoid
			box-shadow: none !important
			border: 1px solid #ccc !important
			-webkit-print-color-adjust: exact
			print-color-adjust: exact
			color-adjust: exact
			.time-box
				-webkit-print-color-adjust: exact
				print-color-adjust: exact
				color-adjust: exact
			.info
				border: 1px solid #ccc !important
				border-left: none !important
				-webkit-print-color-adjust: exact
				print-color-adjust: exact
				color-adjust: exact
			.session-icons
				display: none
		.c-linear-schedule-session
			.info
				background: #fff !important
		.break
			.info
				-webkit-print-color-adjust: exact
				print-color-adjust: exact
				color-adjust: exact
		.c-grid-schedule
			overflow: visible !important
			.timeslice
				position: static !important
				-webkit-print-color-adjust: exact
				print-color-adjust: exact
				color-adjust: exact
				&.gap::before
					display: none
			.c-linear-schedule-session .time-box,
			.break .time-box
				-webkit-print-color-adjust: exact
				print-color-adjust: exact
				color-adjust: exact
		.powered-by
			display: none
</style>

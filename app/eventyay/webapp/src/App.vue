<template lang="pug">
.v-app(:key="`${userLocale}-${userTimezone}`", :class="{'has-background-room': backgroundRoom}", :style="[browserhackStyle, mediaConstraintsStyle]")
	.fatal-connection-error(v-if="fatalConnectionError")
		template(v-if="fatalConnectionError.code === 'world.unknown_world'")
			.mdi.mdi-help-circle
			h1 {{ $t('App:fatal-connection-error:world.unknown_world:headline') }}
		template(v-else-if="fatalConnectionError.code === 'connection.replaced'")
			.mdi.mdi-alert-octagon
			h1 {{ $t('App:fatal-connection-error:connection.replaced:headline') }}
			bunt-button(@click="reload") {{ $t('App:fatal-connection-error:connection.replaced:action') }}
		template(v-else-if="['auth.denied', 'auth.invalid_token', 'auth.missing_token', 'auth.expired_token'].includes(fatalConnectionError.code)")
			.mdi.mdi-alert-octagon
			h1 {{ $t('App:fatal-connection-error:' + fatalConnectionError.code + ':headline') }}
				br
				small {{ $t('App:fatal-connection-error:' + fatalConnectionError.code + ':text') }}
			bunt-button(v-if="fatalConnectionError.code != 'auth.missing_token'", @click="clearTokenAndReload") {{ $t('App:fatal-connection-error:' + fatalConnectionError.code + ':action') }}
		template(v-else)
			h1 {{ $t('App:fatal-connection-error:else:headline') }}
		p.code error code: {{ fatalConnectionError.code }}
	template(v-else-if="world")
		// AppBar stays fixed; only main content shifts
		app-bar(@toggle-sidebar="toggleSidebar")
		.app-content(:class="{'sidebar-open': showSidebar}", role="main", tabindex="-1")
			// router-view no longer carries role=main; main landmark is the scroll container
			router-view(:key="!$route.path.startsWith('/admin') ? $route.fullPath : null")
			//- defining keys like this keeps the playing dom element alive for uninterupted transitions
			media-source(v-if="roomHasMedia && user.profile.greeted", ref="primaryMediaSource", :room="room", :key="room.id", role="main")
			media-source(v-if="call", ref="channelCallSource", :call="call", :background="call.channel !== $route.params.channelId", :key="call.id", @close="$store.dispatch('chat/leaveCall')")
			media-source(v-else-if="backgroundRoom", ref="backgroundMediaSource", :room="backgroundRoom", :background="true", :key="backgroundRoom.id", @close="backgroundRoom = null")
			#media-source-iframes
			notifications(:hasBackgroundMedia="!!backgroundRoom")
			.disconnected-warning(v-if="!connected") {{ $t('App:disconnected-warning:text') }}
			transition(name="prompt")
				greeting-prompt(v-if="!user.profile.greeted")
			.native-permission-blocker(v-if="askingPermission")
		rooms-sidebar(:show="showSidebar", @close="showSidebar = false")
	.connecting(v-else-if="!fatalError")
		bunt-progress-circular(size="huge")
		.details(v-if="socketCloseCode == 1006") {{ $t('App:error-code:1006') }}
		.details(v-if="socketCloseCode") {{ $t('App:error-code:text') }}: {{ socketCloseCode }}
	.fatal-error(v-if="fatalError") {{ fatalError.message }}
</template>
<script>
import { mapState } from 'vuex'
import AppBar from 'components/AppBar'
import RoomsSidebar from 'components/RoomsSidebar'
import MediaSource from 'components/MediaSource'
import Notifications from 'components/notifications'
import GreetingPrompt from 'components/profile/GreetingPrompt'

const mediaModules = ['livestream.native', 'livestream.youtube', 'livestream.iframe', 'call.bigbluebutton', 'call.janus', 'call.zoom']
const stageToolModules = ['livestream.native', 'livestream.youtube', 'livestream.iframe', 'call.janus']
const chatbarModules = ['chat.native', 'question', 'poll']

export default {
	components: { AppBar, RoomsSidebar, MediaSource, GreetingPrompt, Notifications },
	data() {
		return {
			backgroundRoom: null,
			showSidebar: false,
			windowHeight: null
		}
	},
	computed: {
		...mapState(['fatalConnectionError', 'fatalError', 'connected', 'socketCloseCode', 'world', 'rooms', 'user', 'mediaSourcePlaceholderRect', 'userLocale', 'userTimezone']),
		...mapState('notifications', ['askingPermission']),
		...mapState('chat', ['call']),
		room() {
			const routeName = this.$route?.name
			if (!routeName) return
			if (routeName.startsWith && routeName.startsWith('admin')) return
			if (routeName === 'home') return this.rooms?.[0]
			return this.rooms?.find(room => room.id === this.$route.params.roomId)
		},
		// TODO since this is used EVERYWHERE, use provide/inject?
		modules() {
			return this.room?.modules.reduce((acc, module) => {
				acc[module.type] = module
				return acc
			}, {})
		},
		roomHasMedia() {
			return this.room?.modules.some(module => mediaModules.includes(module.type))
		},
		stageStreamCollapsed() {
			if (this.$mq.above.m) return false
			return this.mediaSourceRefs.primary?.$refs.livestream ? !this.mediaSourceRefs.primary.$refs.livestream.playing : false
		},
		// force open sidebar on medium screens on home page (with no media) so certain people can find the menu
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
				primary: this.$refs.primaryMediaSource,
				background: this.$refs.backgroundMediaSource,
				channel: this.$refs.channelCallSource
			}
		}
	},
	watch: {
		world: 'worldChange',
		rooms: 'roomListChange',
		room: 'roomChange',
		call: 'callChange',
		$route() {
			// Always close the sidebar after navigation for consistent drawer UX on all screen sizes
			this.showSidebar = false
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
		onKeydown(e) {
			if ((e.key === 'Escape' || e.key === 'Esc') && this.showSidebar) {
				this.showSidebar = false
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
			this.showSidebar = !this.showSidebar
		},
		onGlobalPointerDown(event) {
			if (!this.showSidebar) return
			const sidebarEl = document.querySelector('.c-rooms-sidebar')
			const hamburgerEl = document.querySelector('.c-app-bar .hamburger')
			if (sidebarEl?.contains(event.target) || hamburgerEl?.contains(event.target)) return
			this.showSidebar = false
		},
		clearTokenAndReload() {
			localStorage.removeItem('token')
			location.reload()
		},
		reload() {
			location.reload()
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
			this.$store.dispatch('changeRoom', newRoom)
			const isExclusive = module => module.type === 'call.bigbluebutton' || module.type === 'call.zoom'
			if (!this.$mq.above.m) return // no background rooms for mobile
			if (this.call) return // When a DM call is running, we never want background media
			const newRoomHasMedia = newRoom && newRoom.modules && newRoom.modules.some(module => mediaModules.includes(module.type))
			// We treat "undefined / not callable" as true to avoid race conditions.
			let primaryWasPlaying = true
			const primaryRef = this.mediaSourceRefs.primary
			if (typeof primaryRef?.isPlaying === 'function') {
				const result = primaryRef.isPlaying()
				if (result === false) primaryWasPlaying = false
			}
			if (oldRoom &&
				this.rooms.includes(oldRoom) &&
				!this.backgroundRoom &&
				oldRoom.modules.some(module => mediaModules.includes(module.type)) &&
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
	--sidebar-width: 280px
	--pretalx-clr-primary: var(--clr-primary)
	.c-app-bar
		flex: none
	.app-content
		flex: auto
		min-height: 0
		position: relative
		// Smoothly shift content when sidebar opens/closes
		transition: margin-left .3s ease, width .3s ease
		width: 100vw
		height: calc(var(--vh100) - 48px)
		overflow-y: auto
		-webkit-overflow-scrolling: touch
		overscroll-behavior: contain
		&.sidebar-open
			margin-left: var(--sidebar-width)
			width: calc(100vw - var(--sidebar-width))
	.c-room-header
		height: calc(var(--vh100) - 48px)
	> .bunt-progress-circular
		position: fixed
		top: 50%
		left: 50%
		transform: translate(-50%, -50%)
	.disconnected-warning, .fatal-error
		position: fixed
		top: 0
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
		top: 0
		left: 0
		width: 100vw
		height: var(--vh100)
		z-index: 2000
		background-color: $clr-secondary-text-light
	#media-source-iframes
		position: absolute
		width: 0
		height: 0
</style>

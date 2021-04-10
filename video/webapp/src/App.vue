<template lang="pug">
#app(:class="{'has-background-room': backgroundRoom, 'override-sidebar-collapse': overrideSidebarCollapse}", :style="[themeVariables, browserhackStyle, mediaConstraintsStyle]")
	.fatal-connection-error(v-if="fatalConnectionError")
		template(v-if="fatalConnectionError.code === 'world.unknown_world'")
			.mdi.mdi-help-circle
			h1 {{ $t('App:fatal-connection-error:world.unknown_world:headline') }}
		template(v-else-if="fatalConnectionError.code === 'connection.replaced'")
			.mdi.mdi-alert-octagon
			h1 {{ $t('App:fatal-connection-error:connection.replaced:headline') }}
			bunt-button(@click="reload") {{ $t('App:fatal-connection-error:connection.replaced:action') }}
		template(v-else-if="fatalConnectionError.code === 'auth.denied' || fatalConnectionError.code === 'auth.missing_id_or_token'")
			.mdi.mdi-alert-octagon
			h1 {{ $t('App:fatal-connection-error:auth.denied:headline') }}
				br
				| {{ $t('App:fatal-connection-error:auth.denied:text') }}
		template(v-else)
			h1 {{ $t('App:fatal-connection-error:else:headline') }}
		p.code error code: {{ fatalConnectionError.code }}
	template(v-else-if="world")
		app-bar(v-if="$mq.below['l']", @toggleSidebar="toggleSidebar")
		transition(name="backdrop")
			.sidebar-backdrop(v-if="$mq.below['l'] && showSidebar && !overrideSidebarCollapse", @pointerup="showSidebar = false")
		rooms-sidebar(:show="$mq.above['l'] || showSidebar || overrideSidebarCollapse", @close="showSidebar = false")
		router-view(:key="$route.fullPath")
		//- defining keys like this keeps the playing dom element alive for uninterupted transitions
		media-source(v-if="roomHasMedia && user.profile.greeted", ref="primaryMediaSource", :room="room", :key="room.id")
		media-source(v-if="call", ref="channelCallSource", :call="call", :background="call.channel !== $route.params.channelId", :key="call.id", @close="$store.dispatch('chat/leaveCall')")
		media-source(v-else-if="backgroundRoom", ref="backgroundMediaSource", :room="backgroundRoom", :background="true", :key="backgroundRoom.id", @close="backgroundRoom = null")
		notifications(:has-background-media="!!backgroundRoom")
		.disconnected-warning(v-if="!connected") {{ $t('App:disconnected-warning:text') }}
		transition(name="prompt")
			greeting-prompt(v-if="!user.profile.greeted")
		.native-permission-blocker(v-if="askingPermission")
	.connecting(v-else-if="!fatalError")
		bunt-progress-circular(size="huge")
		.details(v-if="socketCloseCode == 1006") {{ $t('App:error-code:1006') }}
		.details(v-if="socketCloseCode") {{ $t('App:error-code:text') }}: {{ socketCloseCode }}
	.fatal-error(v-if="fatalError") {{ fatalError.message }}
</template>
<script>
import { mapState } from 'vuex'
import { themeVariables } from 'theme'
import AppBar from 'components/AppBar'
import RoomsSidebar from 'components/RoomsSidebar'
import MediaSource from 'components/MediaSource'
import Notifications from 'components/notifications'
import GreetingPrompt from 'components/profile/GreetingPrompt'

const mediaModules = ['livestream.native', 'call.bigbluebutton', 'call.janus', 'call.zoom', 'livestream.youtube']
const stageToolModules = ['livestream.native', 'call.janus', 'livestream.youtube']
const chatbarModules = ['chat.native', 'question']

export default {
	components: { AppBar, RoomsSidebar, MediaSource, GreetingPrompt, Notifications },
	data () {
		return {
			themeVariables,
			backgroundRoom: null,
			showSidebar: false,
			windowHeight: null
		}
	},
	computed: {
		...mapState(['fatalConnectionError', 'fatalError', 'connected', 'socketCloseCode', 'world', 'rooms', 'user']),
		...mapState('notifications', ['askingPermission']),
		...mapState('chat', ['call']),
		room () {
			if (this.$route.name.startsWith('admin')) return
			if (this.$route.name === 'home') return this.rooms?.[0]
			return this.rooms?.find(room => room.id === this.$route.params.roomId)
		},
		roomHasMedia () {
			return this.room?.modules.some(module => mediaModules.includes(module.type))
		},
		// force open sidebar on medium screens on home page (with no media) so certain people can find the menu
		overrideSidebarCollapse () {
			return this.$mq.below.l &&
				this.$mq.above.m &&
				this.$route.name === 'home' &&
				!this.roomHasMedia
		},
		// safari cleverly includes the address bar cleverly in 100vh
		mediaConstraintsStyle () {
			const hasStageTools = this.room?.modules.some(module => stageToolModules.includes(module.type))
			const hasChatbar = (
				(this.room?.modules.length > 1 && this.room?.modules.some(module => chatbarModules.includes(module.type))) ||
				(this.call && this.call.channel === this.$route.params.channelId)
			)

			return {
				'--chatbar-width': hasChatbar ? '380px' : '0px',
				'--mobile-media-height': hasChatbar ? '40vh' : (hasStageTools ? 'calc(100vh - 48px - 2 * 56px)' : 'calc(100vh - 48px - 56px)'),
				'--has-stagetools': hasStageTools ? '1' : '0',
			}
		},
		browserhackStyle () {
			return {
				'--vh100': this.windowHeight + 'px',
				'--vh': this.windowHeight && (this.windowHeight / 100) + 'px'
			}
		}
	},
	watch: {
		world: 'worldChange',
		rooms: 'roomListChange',
		room: 'roomChange',
		call: 'callChange',
		$route () {
			this.showSidebar = false
		}
	},
	mounted () {
		this.windowHeight = window.innerHeight
		window.addEventListener('resize', this.onResize)
		window.addEventListener('focus', this.onFocus, true)
	},
	destroyed () {
		window.removeEventListener('resize', this.onResize)
		window.removeEventListener('focus', this.onFocus)
	},
	methods: {
		onResize () {
			this.windowHeight = window.innerHeight
		},
		onFocus () {
			this.$store.dispatch('notifications/clearDesktopNotifications')
		},
		toggleSidebar () {
			this.showSidebar = !this.showSidebar
		},
		reload () {
			location.reload()
		},
		worldChange () {
			// initial connect
			document.title = this.world.title
		},
		callChange () {
			if (this.call) {
				// When a DM call starts, all other background media stops
				this.backgroundRoom = null
			}
		},
		roomChange (newRoom, oldRoom) {
			// HACK find out why this is triggered often
			if (newRoom === oldRoom) return
			// TODO non-room urls
			let title = this.world.title
			if (this.room) {
				title += ` | ${this.room.name}`
			}
			document.title = title
			this.$store.dispatch('changeRoom', newRoom)
			const isExclusive = module => module.type === 'call.bigbluebutton' || module.type === 'call.zoom'
			if (!this.$mq.above.m) return // no background rooms for mobile
			if (this.call) return // When a DM call is running, we never want background media
			if (oldRoom &&
				this.rooms.includes(oldRoom) &&
				!this.backgroundRoom &&
				oldRoom.modules.some(module => mediaModules.includes(module.type)) &&
				this.$refs.primaryMediaSource.isPlaying() &&
				// don't background bbb room when switching to new bbb room
				!(newRoom?.modules.some(isExclusive) && oldRoom?.modules.some(isExclusive))
			) {
				this.backgroundRoom = oldRoom
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
		roomListChange () {
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
#app
	display: grid
	grid-template-columns: var(--sidebar-width) auto
	grid-template-rows: auto
	grid-template-areas: "rooms-sidebar main"
	--sidebar-width: 280px

	.c-app-bar
		grid-area: app-bar
	.c-rooms-sidebar
		grid-area: rooms-sidebar
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
		height: 100vh
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

	+below('l')
		&.override-sidebar-collapse
			grid-template-rows: 48px auto
			grid-template-areas: "app-bar app-bar" "rooms-sidebar main"
		&:not(.override-sidebar-collapse)
			grid-template-columns: auto
			grid-template-rows: 48px auto
			grid-template-areas: "app-bar" "main"

			.sidebar-backdrop
				position: fixed
				top: 0
				left: 0
				height: var(--vh100)
				width: 100vw
				z-index: 900
				background-color: $clr-secondary-text-light
				&.backdrop-enter-active, &.backdrop-leave-active
					transition: opacity .2s
				&.backdrop-enter, &.backdrop-leave-to
					opacity: 0
			.fatal-connection-error
				.mdi
					font-size: 128px
				h1
					font-size: 24px
</style>

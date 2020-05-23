<template lang="pug">
#app(:style="themeVariables")
	template(v-if="world")
		app-bar(v-if="$mq.below['s']", @toggleSidebar="toggleSidebar")
		transition(name="backdrop")
			.sidebar-backdrop(v-if="$mq.below['s'] && showSidebar", @pointerup="showSidebar = false")
		rooms-sidebar(:show="$mq.above['s'] || showSidebar", @editProfile="showProfilePrompt = true", @createRoom="showStageCreationPrompt = true", @createChat="showChatCreationPrompt = true",  @close="showSidebar = false")
		router-view(:key="$route.fullPath")
		livestream.global-stream(v-if="$mq.above['s'] && streamingRoom", ref="globalStream", :room="streamingRoom", :module="streamingRoom.modules.find(module => module.type === 'livestream.native')", :size="streamingRoom === room ? 'normal' : 'mini'", @close="closeMiniStream", :key="streamingRoom.id")
		transition(name="prompt")
			profile-prompt(v-if="!user.profile.display_name || showProfilePrompt", @close="showProfilePrompt = false")
			create-stage-prompt(v-else-if="showStageCreationPrompt", @close="showStageCreationPrompt = false")
			create-chat-prompt(v-else-if="showChatCreationPrompt", @close="showChatCreationPrompt = false")
		.disconnected-warning(v-if="!connected") {{ $t('app:no-connection') }}
	bunt-progress-circular(v-else, size="huge")
</template>
<script>
import { mapState } from 'vuex'
import { themeVariables } from 'theme'
import AppBar from 'components/AppBar'
import RoomsSidebar from 'components/RoomsSidebar'
import ProfilePrompt from 'components/ProfilePrompt'
import CreateStagePrompt from 'components/CreateStagePrompt'
import CreateChatPrompt from 'components/CreateChatPrompt'
import Livestream from 'components/Livestream'

export default {
	components: { AppBar, RoomsSidebar, Livestream, ProfilePrompt, CreateStagePrompt, CreateChatPrompt },
	data () {
		return {
			themeVariables,
			showSidebar: false,
			showProfilePrompt: false,
			showStageCreationPrompt: false,
			showChatCreationPrompt: false
		}
	},
	computed: {
		...mapState(['connected', 'world', 'user', 'streamingRoom']),
		room () {
			return this.$store.state.rooms?.find(room => room.id === this.$route.params.roomId)
		},
	},
	watch: {
		room: 'roomChange',
		$route () {
			this.showSidebar = false
		}
	},
	methods: {
		toggleSidebar () {
			this.showSidebar = !this.showSidebar
		},
		roomChange () {
			if (this.$mq.above.s && this.room && !this.streamingRoom && this.room.modules.some(module => module.type === 'livestream.native')) {
				this.$store.dispatch('streamRoom', {room: this.room})
			}
			if (this.room && this.streamingRoom && !this.$refs.globalStream?.playing) {
				if (this.room.modules.some(module => module.type === 'livestream.native')) {
					this.$store.dispatch('streamRoom', {room: this.room})
				} else {
					// TODO don't close when mini player is paused and changing rooms
					this.$store.dispatch('streamRoom', {room: null})
				}
			}
		},
		closeMiniStream () {
			this.$store.dispatch('streamRoom', {room: null})
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
	--chatbar-width: 380px
	.c-app-bar
		grid-area: app-bar
	.c-rooms-sidebar
		grid-area: rooms-sidebar
	> .bunt-progress-circular
		position: fixed
		top: 50%
		left: 50%
		transform: translate(-50%, -50%)
	.global-stream
		position: fixed
		transition: all .2s ease
		&.size-mini
			bottom: calc(100vh - 128px - 4px)
			right: 4px
		&:not(.size-mini)
			bottom: 56px
			right: var(--chatbar-width)
			width: calc(100vw - var(--sidebar-width) - var(--chatbar-width))
			height: calc(100vh - 56px * 2)
	.prompt-enter-active, .prompt-leave-active
		transition: opacity .5s
	.prompt-enter, .prompt-leave-to
		opacity: 0
	.disconnected-warning
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

	+below('s')
		grid-template-columns: auto
		grid-template-rows: 48px auto
		grid-template-areas: "app-bar" "main"

		.sidebar-backdrop
			position: fixed
			top: 0
			left: 0
			height: 100vh
			width: 100vw
			z-index: 999
			background-color: $clr-secondary-text-light
			&.backdrop-enter-active, &.backdrop-leave-active
				transition: opacity .2s
			&.backdrop-enter, &.backdrop-leave-to
				opacity: 0
</style>

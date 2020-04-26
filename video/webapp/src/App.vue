<template lang="pug">
#app
	template(v-if="world")
		//- app-bar
		rooms-sidebar(@editProfile="showProfilePrompt = true")
		router-view
		livestream.global-stream(v-if="streamingRoom", :room="streamingRoom", :module="streamingRoom.modules.find(module => module.type === 'livestream.native')", :size="streamingRoom === room ? 'normal' : 'mini'", @close="closeMiniStream")
		transition(name="profile-prompt")
			profile-prompt(v-if="!user.profile.display_name || showProfilePrompt", @close="showProfilePrompt = false")
	bunt-progress-circular(v-else, size="huge")
</template>
<script>
import { mapState } from 'vuex'
import AppBar from 'components/AppBar'
import RoomsSidebar from 'components/RoomsSidebar'
import ProfilePrompt from 'components/ProfilePrompt'
import Livestream from 'components/Livestream'

export default {
	components: { AppBar, RoomsSidebar, Livestream, ProfilePrompt },
	data () {
		return {
			showProfilePrompt: false
		}
	},
	computed: {
		...mapState(['world', 'user', 'streamingRoom']),
		room () {
			return this.$store.state.rooms?.find(room => room.id === this.$route.params.roomId)
		},
	},
	watch: {
		room: 'roomChange'
	},
	methods: {
		roomChange () {
			if (this.room && !this.streamingRoom && this.room.modules.some(module => module.type === 'livestream.native')) {
				this.$store.dispatch('streamRoom', {room: this.room})
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
			top: 4px
			right: 4px
		&:not(.size-mini)
			bottom: 0
			left: var(--sidebar-width)
			width: calc(100vw - var(--sidebar-width) - var(--chatbar-width))
			height: calc(100vh - 112px)
	.profile-prompt-enter-active, .profile-prompt-leave-active
		transition: opacity .5s
	.profile-prompt-enter, .profile-prompt-leave-to
		opacity: 0
</style>

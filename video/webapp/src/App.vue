<template lang="pug">
#app
	template(v-if="world")
		//- app-bar
		rooms-sidebar
		router-view
		transition(name="profile-prompt")
			profile-prompt(v-if="!user.profile.display_name")
	bunt-progress-circular(v-else, size="huge")
</template>
<script>
import { mapState } from 'vuex'
import AppBar from 'components/AppBar'
import RoomsSidebar from 'components/RoomsSidebar'
import ProfilePrompt from 'components/ProfilePrompt'

export default {
	components: { AppBar, RoomsSidebar, ProfilePrompt },
	computed: {
		...mapState(['world', 'user'])
	}
}
</script>
<style lang="stylus">
#app
	display: grid
	grid-template-columns: 380px auto
	grid-template-rows: auto
	grid-template-areas: "rooms-sidebar main"

	.c-app-bar
		grid-area: app-bar
	.c-rooms-sidebar
		grid-area: rooms-sidebar
	> .bunt-progress-circular
		position: fixed
		top: 50%
		left: 50%
		transform: translate(-50%, -50%)

	.profile-prompt-enter-active, .profile-prompt-leave-active
		transition: opacity .5s
	.profile-prompt-enter, .profile-prompt-leave-to
		opacity: 0
</style>

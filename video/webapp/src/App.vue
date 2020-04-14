<template lang="pug">
#app
	template(v-if="event")
		app-bar
		rooms-sidebar
		router-view
		profile-prompt(v-if="!user.profile")
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
		...mapState(['event', 'user'])
	}
}
</script>
<style lang="stylus">
#app
	display: grid
	grid-template-columns: 280px auto
	grid-template-rows: 48px auto
	grid-template-areas: "app-bar app-bar" "rooms-sidebar main"

	.c-app-bar
		grid-area: app-bar
	.c-rooms-sidebar
		grid-area: rooms-sidebar
	> .bunt-progress-circular
		position: fixed
		top: 50%
		left: 50%
		transform: translate(-50%, -50%)
</style>

<template lang="pug">
#app
	template(v-if="event")
		app-bar
		rooms-sidebar
		router-view
	bunt-progress-circular(v-else, size="huge")
</template>
<script>
import { mapState } from 'vuex'
import AppBar from 'components/AppBar'
import RoomsSidebar from 'components/RoomsSidebar'

export default {
	components: { AppBar, RoomsSidebar },
	computed: {
		...mapState(['event'])
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

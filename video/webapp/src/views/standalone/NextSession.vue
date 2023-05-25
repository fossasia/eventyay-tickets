<template lang="pug">
.c-standalone-next-session(v-if="nextSession")
	h2 {{ $t('standalone/NextSession:header') }}
	Session(:session="nextSession")
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import { Session } from '@pretalx/schedule'

export default {
	components: {Session},
	props: {
		room: Object
	},
	data () {
		return {
		}
	},
	computed: {
		...mapState(['now']),
		...mapGetters('schedule', ['sessions', 'favs']),
		nextSession () {
			if (!this.sessions) return
			// next session in this room
			return this.sessions.find(session => session.room === this.room && session.start.isAfter(this.now))
		},
	},
}
</script>
<style lang="stylus">
.c-standalone-next-session
	display: flex
	flex-direction: column
	align-items: center
	scale: 2
	.c-linear-schedule-session
		min-width: 500px
</style>

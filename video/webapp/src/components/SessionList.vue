<template lang="pug">
.c-session-list(v-if="sessions")
	.session(v-for="{session, state}, index of sessionsWithState", :class="{live: state.isLive}")
		.speaker-avatars
			template(v-for="speaker of session.speakers")
				img(v-if="speaker.avatar", :src="speaker.avatar")
				identicon(v-else, :id="speaker.name")
		.info
			.title-time
				.title {{ $localize(session.title) }}
				.time {{ state.timeString }}
			.speakers-room
				.speakers {{ session.speakers ? session.speakers.map(s => s.name).join(', ') : '' }}
				.room {{ $localize(session.room.name) }}
</template>
<script>
import { mapState } from 'vuex'
import moment from 'lib/timetravelMoment'

export default {
	components: {},
	props: {
		sessions: Array
	},
	data () {
		return {
		}
	},
	computed: {
		...mapState(['now', 'rooms']),
		sessionsWithState () {
			return this.sessions.map(session => ({session, state: this.getSessionState(session)}))
		}
	},
	async created () {},
	async mounted () {
		await this.$nextTick()
	},
	methods: {
		getSessionState (session) {
			if (session.start.isBefore(this.now)) {
				return {
					isLive: true,
					timeString: 'live'
				}
			}
			// if (session.start.isBefore(this.now)) {
			// 	return {
			// 		timeString: 'starting soon'
			// 	}
			// }
			return {
				timeString: moment.duration(session.start.diff(this.now)).humanize(true).replace('minutes', 'mins')
			}
		}
	}
}
</script>
<style lang="stylus">
.c-session-list
	display: flex
	flex-direction: column
	border: border-separator()
	.session
		height: 56px
		position: relative
		padding: 4px 0
		box-sizing: border-box
		display: flex
		cursor: pointer
		&:not(:last-child)
			border-bottom: border-separator()
		&:hover
			background-color: $clr-grey-100
		.speaker-avatars
			flex: none
			min-width: 8px
			> *:not(:first-child)
				margin-left: -28px
			img
				background-color: $clr-white
				border-radius: 50%
				height: 48px
				width: 48px
				margin: 0 8px 0 4px
				object-fit: cover
		.info
			flex: auto
			min-width: 0
			display: flex
			flex-direction: column
			justify-content: space-between
		.title-time
			flex: none
			display: flex
			align-items: center
			overflow: hidden
		.title
			flex: auto
			// font-weight: 600
			// line-height: 32px
			line-height: 28px
			ellipsis()
		.time
			flex: none
			background-color: $clr-blue-grey-500
			color: $clr-primary-text-dark
			padding: 2px 4px
			margin: 0 4px 4px
			border-radius: 4px
		.speakers-room
			display: flex
			align-items: baseline
			margin-right: 4px
		.speakers, .room
			flex: 1
			color: $clr-secondary-text-light
			ellipsis()
		.room
			margin-left: 4px
			text-align: right
		&.live .time
			background-color: $clr-danger
</style>

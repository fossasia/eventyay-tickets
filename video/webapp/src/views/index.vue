<template lang="pug">
.c-home
	.hero
		img(src="/venueless-logo-full-white.svg")
	.description
		h2 Welcome to this example event!
		h3 Schedule
	.schedule
		.session(v-for="session, index of nextSessions", :class="{live: session.start.isBefore(now)}")
			img.preview(:src="`https://picsum.photos/64?v=${index}`")
			.time {{ session.start.isBefore(now) ? 'live now' : moment.duration(session.start.diff(now)).humanize(true).replace('minutes', 'mins') }}
			.info
				.title {{ session.title }}
				.speakers {{ session.speakers.map(s => s.name).join(', ')}}
			.room {{ session.room.name }}
</template>
<script>
import { mapGetters } from 'vuex'
import moment from 'lib/timetravelMoment'

export default {
	components: {},
	data () {
		return {
			moment,
			now: moment()
		}
	},
	computed: {
		...mapGetters(['flatSchedule']),
		nextSessions () {
			if (!this.flatSchedule) return
			// current or next sessions per room
			const sessions = []
			for (const session of this.flatSchedule.sessions) {
				if (session.end.isBefore(this.now) || sessions.length > 5) continue
				sessions.push(session)
			}
			return sessions
		}
	},
	created () {
	},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {}
}
</script>
<style lang="stylus">
.c-home
	background-color: $clr-white
	.hero
		height: calc(var(--vh) * 30)
		display: flex
		justify-content: center
		background-color: var(--clr-primary)
		img
			height: 100%
			object-fit: contain
	.description
		padding: 0 16px
	.schedule
		display: flex
		flex-direction: column
		width: 420px
		margin: 16px
		border: border-separator()
		.session
			height: 56px
			position: relative
			padding: 4px 0
			box-sizing: border-box
			display: flex
			&:not(:last-child)
				border-bottom: border-separator()
			.preview
				border-radius: 50%
				height: 48px
				width: 48px
				margin: 0 8px 0 4px
			.title
				// font-weight: 600
				// line-height: 32px
				line-height: 28px
			.speakers
				color: $clr-secondary-text-light
			.time
				position: absolute
				top: 4px
				right: 4px
				background-color: $clr-blue-grey-500
				color: $clr-primary-text-dark
				padding: 2px 4px
				border-radius: 4px
			.room
				color: $clr-secondary-text-light
				position: absolute
				bottom: 8px
				right: 6px
			&.live .time
				background-color: $clr-danger
</style>

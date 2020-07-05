<template lang="pug">
.c-home(v-scrollbar.y="")
	.hero
		img(src="/venueless-logo-full-white.svg")
	.content
		.description
			h2 Welcome to this example event!
			p You might notice that the dates for the current sessions are not actually your current time and that time does not progress. That's because we froze time – only in this demo of course – with the power of programming!
			p Have a look around!
		.sidebar
			.header
				h3 Schedule
				router-link(:to="{name: 'schedule'}") full schedule
			.sessions
				.session(v-for="{session, state}, index of nextSessions", :class="{live: state.isLive}")
					img.preview(:src="`https://picsum.photos/64?v=${index}`")
					.time {{ state.timeString }}
					.info
						.title {{ session.title }}
						.speakers {{ session.speakers.map(s => s.name).join(', ')}}
					.room {{ session.room.name }}
			.header
				h3 Sponsors
				router-link(:to="{name: 'schedule'}") all sponsors
			.sponsors
				.sponsor(v-for="sponsor of sponsors")
					img(:src="sponsor.logo")

</template>
<script>
import { mapState, mapGetters } from 'vuex'
import moment from 'lib/timetravelMoment'

export default {
	components: {},
	data () {
		return {
			moment,
			sponsors: [{
				name: 'pretix',
				logo: '/sponsors/pretix.svg'
			}, {
				name: 'pretalx',
				logo: '/sponsors/pretalx.svg'
			}]
		}
	},
	computed: {
		...mapState(['now']),
		...mapGetters(['flatSchedule']),
		nextSessions () {
			if (!this.flatSchedule) return
			const getSessionState = (session) => {
				if (session.room.schedule_data) {
					return {
						isLive: true,
						timeString: 'live now'
					}
				}
				if (session.start.isBefore(this.now)) {
					return {
						timeString: 'starting soon'
					}
				}
				return {
					timeString: moment.duration(session.start.diff(this.now)).humanize(true).replace('minutes', 'mins')
				}
			}
			// current or next sessions per room
			const sessions = []
			for (const session of this.flatSchedule.sessions) {
				if (session.end.isBefore(this.now) || sessions.length > 5) continue
				sessions.push({session, state: getSessionState(session)})
			}
			return sessions
		}
	}
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
	.content
		display: flex
		justify-content: center
	.description
		padding: 0 16px
		max-width: 560px
	.header
		display: flex
		justify-content: space-between
		align-items: baseline
		height: 56px
		padding: 0 4px
		h3
			margin: 0
			line-height: 56px
	.sidebar
		width: 420px
	.sessions
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
				top: 8px
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
	.sponsors
		.sponsor
			display: flex
			justify-content: center
			padding: 16px
			img
				width: 90%
</style>

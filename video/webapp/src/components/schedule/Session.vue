<template lang="pug">
router-link.c-linear-schedule-session(:style="style", :to="{name: 'schedule:talk', params: {talkId: session.id}}")
	.time-box
		.start {{ startTime }}
		.duration {{ durationMinutes }}min
	.info
		.title {{ session.title }}
		.speakers {{ session.speakers.map(s => s.name).join(', ') }}
		.abstract {{ session.abstract }}
		.bottom-info
			.track(v-if="session.track") {{ getLocalizedString(session.track.name) }}
			.room(v-if="session.room") {{ getLocalizedString(session.room.name) }}
</template>
<script>
import moment from 'lib/timetravelMoment'
import { getLocalizedString } from './utils'

moment.locale('de')
export default {
	props: {
		session: Object
	},
	data () {
		return {
			getLocalizedString
		}
	},
	computed: {
		style () {
			return {
				'--track-color': this.session.track?.color || 'var(--clr-primary)'
			}
		},
		startTime () {
			return moment(this.session.start).format('LT')
		},
		durationMinutes () {
			return moment(this.session.end).diff(this.session.start, 'minutes')
		}
	}
}
</script>
<style lang="stylus">
.c-linear-schedule-session
	display: flex
	min-width: 480px
	min-height: 96px
	margin: 8px
	overflow: hidden
	color: $clr-primary-text-light
	.time-box
		// width: 60px
		background-color: var(--track-color)
		padding: 12px 16px 8px 12px
		border-radius: 6px 0 0 6px
		display: flex
		flex-direction: column
		align-items: center
		.start
			color: $clr-primary-text-dark
			font-size: 16px
			font-weight: 600
			margin-bottom: 8px
		.duration
			color: $clr-secondary-text-dark
	.info
		flex: auto
		display: flex
		flex-direction: column
		padding: 8px
		border: border-separator()
		border-left: none
		border-radius: 0 6px 6px 0
		background-color: $clr-white
		.title
			font-size: 16px
			font-weight: 500
			margin-bottom: 4px
		.speakers
			color: $clr-secondary-text-light
		.abstract
			margin: 8px 0 12px 0
		.bottom-info
			flex: auto
			display: flex
			align-items: flex-end
			justify-content: space-between
			.track
				color: var(--track-color)
			.room
				color: $clr-secondary-text-light
	&:hover
		.info
			border: 1px solid var(--clr-primary)
			border-left: none
			.title
				color: var(--clr-primary)
	+below('m')
		min-width: 0
</style>

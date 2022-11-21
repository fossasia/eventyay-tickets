<template lang="pug">
a.c-linear-schedule-session(:href="linkHref", :style="style", @click="linkClick($event)", target="_blank")
	.time-box
		.start(:class="{'has-ampm': startTime.ampm}")
			.time {{ startTime.time }}
			.ampm(v-if="startTime.ampm") {{ startTime.ampm }}
		.duration {{ durationMinutes }}min
		.buffer
		.is-live(v-if="isLive") live
	.info
		.title {{ $localize(session.title) }}
		.speakers(v-if="session.speakers")
			.avatars
				template(v-for="speaker of session.speakers")
					img(v-if="speaker.avatar", :src="speaker.avatar")
			.names {{ session.speakers.map(s => s.name).join(', ') }}
		.abstract(v-if="showAbstract") {{ session.abstract }}
		.bottom-info
			.track(v-if="session.track") {{ $localize(session.track.name) }}
			.room(v-if="showRoom && session.room") {{ $localize(session.room.name) }}
</template>
<script>
import moment from 'lib/timetravelMoment'
import router from 'router'

export default {
	props: {
		session: Object,
		showAbstract: {
			type: Boolean,
			default: true
		},
		showRoom: {
			type: Boolean,
			default: true
		}
	},
	data () {
		return {
		}
	},
	computed: {
		style () {
			return {
				'--track-color': this.session.track?.color || 'var(--clr-primary)'
			}
		},
		startTime () {
			// check if 12h or 24h locale
			if (moment.localeData().longDateFormat('LT').endsWith(' A')) {
				return {
					time: this.session.start.format('h:mm'),
					ampm: this.session.start.format('A')
				}
			} else {
				return {
					time: moment(this.session.start).format('LT')
				}
			}
		},
		durationMinutes () {
			return moment(this.session.end).diff(this.session.start, 'minutes')
		},
		isLive () {
			return moment(this.session.start).isBefore(this.now) && moment(this.session.end).isAfter(this.now)
		},
		targetRoute () {
			// a room having modules is a good enough indicator for a native room
			if (this.isLive && this.session.room?.modules) {
				return {name: 'room', params: {roomId: this.session.room.id}}
			}
			return {name: 'schedule:talk', params: {talkId: this.session.id}}
		},
		linkHref () {
			if (this.session.url) {
				return this.session.url
			} else {
				return router.resolve(this.targetRoute).href
			}
		}
	},
	methods: {
		async linkClick (event) {
			if (!this.session.url) {
				event.preventDefault()
				await router.push(this.targetRoute)
			}
		}
	}
}
</script>
<style lang="stylus">
.c-linear-schedule-session
	display: flex
	min-width: 360px
	min-height: 96px
	margin: 8px
	overflow: hidden
	color: $clr-primary-text-light
	.time-box
		width: 69px
		box-sizing: border-box
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
			display: flex
			flex-direction: column
			align-items: flex-end
			&.has-ampm
				align-self: stretch
			.ampm
				font-weight: 400
				font-size: 13px
		.duration
			color: $clr-secondary-text-dark
		.buffer
			flex: auto
		.is-live
			align-self: stretch
			text-align: center
			font-weight: 600
			padding: 2px 4px
			border-radius: 4px
			margin: 0 -10px 0 -6px // HACK
			background-color: $clr-danger
			color: $clr-primary-text-dark
			letter-spacing: 0.5px
			text-transform: uppercase
	.info
		flex: auto
		display: flex
		flex-direction: column
		padding: 8px
		border: border-separator()
		border-left: none
		border-radius: 0 6px 6px 0
		background-color: $clr-white
		min-width: 0
		.title
			font-size: 16px
			font-weight: 500
			margin-bottom: 4px
		.speakers
			color: $clr-secondary-text-light
			display: flex
			.avatars
				flex: none
				> *:not(:first-child)
					margin-left: -20px
				img
					background-color: $clr-white
					border-radius: 50%
					height: 24px
					width: @height
					margin: 0 8px 0 0
					object-fit: cover
			.names
				line-height: 24px
		.abstract
			margin: 8px 0 12px 0
			// TODO make this take up more space if available?
			display: -webkit-box
			-webkit-line-clamp: 3
			-webkit-box-orient: vertical
			overflow: hidden
		.bottom-info
			flex: auto
			display: flex
			align-items: flex-end
			.track
				flex: 1
				color: var(--track-color)
				ellipsis()
				margin-right: 4px
			.room
				flex: 1
				text-align: right
				color: $clr-secondary-text-light
				ellipsis()
	&:hover
		.info
			border: 1px solid var(--clr-primary)
			border-left: none
			.title
				color: var(--clr-primary)
	+below('m')
		min-width: 0
</style>

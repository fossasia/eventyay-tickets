<template lang="pug">
.c-linear-schedule-session(:style="style", @pointerdown.stop="$emit('startDragging', {session: session, event: $event})", :class="classes")
	.time-box
		.start(:class="{'has-ampm': startTime.ampm}", v-if="startTime")
			.time {{ startTime.time }}
			.ampm(v-if="startTime.ampm") {{ startTime.ampm }}
		.duration {{ durationPretty }}
	.info
		.title {{ getLocalizedString(session.title) }}
		.speakers(v-if="session.speakers") {{ session.speakers.map(s => s.name).join(', ') }}
		.bottom-info(v-if="!isBreak")
			.track(v-if="session.track") {{ getLocalizedString(session.track.name) }}
	.warning.no-print(v-if="warnings?.length")
		.warning-icon.text-danger
			span(v-if="warnings.length > 1") {{ warnings.length }}
			i.fa.fa-exclamation-triangle
</template>
<script>
import moment from 'moment-timezone'
import MarkdownIt from 'markdown-it'
import { getLocalizedString } from '~/utils'

const markdownIt = MarkdownIt({
	linkify: true,
	breaks: true
})

export default {
	props: {
		session: Object,
		warnings: Array,
		isDragged: Boolean,
		isDragClone: {
			type: Boolean,
			default: false
		},
		overrideStart: {
			type: Object,
			default: null
		}
	},
	inject: {
		eventUrl: { default: null },
		generateSessionLinkUrl: {
			default () {
				return ({eventUrl, session}) => `${eventUrl}talk/${session.id}/`
			}
		}
	},
	data () {
		return {
			getLocalizedString
		}
	},
	computed: {
		link () {
			return this.generateSessionLinkUrl({eventUrl: this.eventUrl, session: this.session})
		},
		isBreak () {
			return !this.session.code
		},
		classes () {
			let classes = []
			if (this.isBreak) classes.push('isbreak')
			else {
				classes.push('istalk')
				if (this.session.state !== "confirmed") classes.push('unconfirmed')
			}
			if (this.isDragged) classes.push('dragging')
			if (this.isDragClone) classes.push('clone')
			return classes
		},
		style () {
			return {
				'--track-color': this.session.track?.color || 'var(--pretalx-clr-primary)'
			}
		},
		startTime () {
			// check if 12h or 24h locale
			const time = this.overrideStart  || this.session.start
			if (!time) return
			if (moment.localeData().longDateFormat('LT').endsWith(' A')) {
				return {
					time: time.format('h:mm'),
					ampm: time.format('A')
				}
			} else {
				return {
					time: moment(time).format('LT')
				}
			}
		},
		durationMinutes () {
			if (!this.session.start) return this.session.duration
			return moment(this.session.end).diff(this.session.start, 'minutes')
		},
		durationPretty () {
			if (!this.durationMinutes) return
			let minutes = this.durationMinutes
			const hours = Math.floor(minutes / 60)
			if (minutes <= 60) {
				return `${minutes}min`
			}
			minutes = minutes % 60
			if (minutes) {
				return `${hours}h${minutes}min`
			}
			return `${hours}h`
		}
	}
}
</script>
<style lang="stylus">
.c-linear-schedule-session
	display: flex
	min-width: 300px
	min-height: 96px
	margin: 8px
	overflow: hidden
	color: $clr-primary-text-light
	position: relative
	cursor: pointer
	&.clone
		z-index: 200
	&.dragging
		filter: opacity(0.3)
		cursor: inherit
	&.unconfirmed
		.time-box
			opacity: 0.5
		.info
			background-image: repeating-linear-gradient(-38deg, $clr-grey-100, $clr-grey-100 10px, $clr-white 10px, $clr-white 20px)
	&.isbreak
		background-color: $clr-grey-200
		border-radius: 6px
		.time-box
			background-color: $clr-grey-500
			.start
				color: $clr-primary-text-dark
			.duration
				color: $clr-secondary-text-dark
		.info
			justify-content: center
			align-items: center
			.title
				font-size: 20px
				color: $clr-secondary-text-light
				align: center
	&.istalk
		.time-box
			background-color: var(--track-color)
			.start
				color: $clr-primary-text-dark
			.duration
				color: $clr-secondary-text-dark
		.info
			border: border-separator()
			border-left: none
			border-radius: 0 6px 6px 0
			background-color: $clr-white
			.title
				font-size: 16px
				margin-bottom: 4px
		&:hover
			.info
				border: 1px solid var(--track-color)
				border-left: none
				.title
					color: var(--pretalx-clr-primary)
	.time-box
		width: 69px
		box-sizing: border-box
		padding: 12px 16px 8px 12px
		border-radius: 6px 0 0 6px
		display: flex
		flex-direction: column
		align-items: center
		.start
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
	.info
		flex: auto
		display: flex
		flex-direction: column
		padding: 8px
		min-width: 0
		.title
			font-weight: 500
		.speakers
			color: $clr-secondary-text-light
		.bottom-info
			flex: auto
			display: flex
			align-items: flex-end
			.track
				flex: 1
				color: var(--track-color)
				ellipsis()
				margin-right: 4px
	.warning
		position: absolute
		top: 0
		right: 0
		padding: 4px 4px
		margin: 4px
		color: #b23e65
		font-size: 16px
		.warning-icon span
			padding-right: 4px
@media print
	.c-linear-schedule-session.isbreak
		border: 2px solid $clr-grey-300 !important
	.c-linear-schedule-session.istalk .time-box
		border: 2px solid var(--track-color) !important
	.c-linear-schedule-session.istalk .info
		border-right: 2px solid var(--track-color) !important
		border-top: 2px solid var(--track-color) !important
		border-bottom: 2px solid var(--track-color) !important
</style>

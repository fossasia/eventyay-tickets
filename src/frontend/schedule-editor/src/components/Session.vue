<template lang="pug">
.c-linear-schedule-session(:style="style", :target="linkTarget", @pointerdown.stop="$emit('startDragging', {session: session, event: $event})", :class="classes")
	.time-box(v-if="!isBreak")
		.start(:class="{'has-ampm': startTime.ampm}", v-if="startTime")
			.time {{ startTime.time }}
			.ampm(v-if="startTime.ampm") {{ startTime.ampm }}
		.duration {{ durationPretty }}
	.info
		.title {{ getLocalizedString(session.title) }}
		.speakers(v-if="session.speakers") {{ session.speakers.map(s => s.name).join(', ') }}
		.bottom-info
			.track(v-if="session.track") {{ getLocalizedString(session.track.name) }}
			.room(v-if="showRoom && session.room") {{ getLocalizedString(session.room.name) }}

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
		isDragged: Boolean,
		isDragClone: {
			type: Boolean,
			default: false
		},
		showRoom: {
			type: Boolean,
			default: true
		},
	},
	inject: {
		eventUrl: { default: null },
		linkTarget: { default: '_self' },
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
			else classes.push('istalk')
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
			if (!this.session.start) return
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
			if (!this.session.start) return this.session.duration
			return moment(this.session.end).diff(this.session.start, 'minutes')
		},
		durationPretty () {
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
	&.isbreak
		// border: border-separator()
		background-color: $clr-grey-200
		border-radius: 6px
		display: flex
		justify-content: center
		align-items: center
		.info .title
			font-size: 20px
			font-weight: 500
			color: $clr-secondary-text-light
			align: center
	&.istalk
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
				border: 1px solid var(--track-color)
				border-left: none
				.title
					color: var(--pretalx-clr-primary)
		// +below('m')
		//	min-width: 0
</style>

<template lang="pug">
a.pretalx-schedule-talk(
	:class="{active: isActive, break: isBreak}"
	:id="'pretalx-' + talk.slug || 'break'"
	:style="style"
	:data-time="timeDisplay"
	:data-start="talk.start"
	:data-end="talk.end"
	target="_blank"
	rel="noopener"
	:href="talkUrl"
)
	.pretalx-schedule-talk-content
		span.fa-stack(v-if="talk.do_not_record")
			i.fa.fa-video-camera.fa-stack-1x
			i.fa.fa-ban.do-not-record.fa-stack-2x(aria-hidden="true")
		span.pretalx-schedule-talk-title(v-if="!isBreak") {{ talk.title }}
		span.pretalx-schedule-break-title(v-else="") {{ talk.title }}
		span.pretalx-schedule-talk-speakers(v-if="talk.display_speaker_names") ({{ talk.display_speaker_names }})
		br
</template>
<script>
import { mapState } from 'vuex'
import moment from 'moment'

export default {
	name: 'pretalx-schedule-talk',
	props: {
		talk: Object,
		track: Object,
		startOfDay: Object
	},
	computed: {
		...mapState(['schedule']), // TODO leaky
		talkUrl () {
			const baseUrl = this.schedule.base_url.split('schedule/')[0]
			return this.talk.slug ? (baseUrl + 'talk/' + this.talk.slug) : '#'
		},
		startMinutes () {
			const date = moment(this.talk.date)
			return date.diff(this.startOfDay, 'minutes')
		},
		durationMinutes () {
			const duration = moment.duration(this.talk.duration)
			return duration.minutes()
		},
		style () {
			return {
				'--start-minutes': this.startMinutes,
				'--duration-minutes': this.durationMinutes,
				/* 'min-height': (this.talk.height >= 30 ? this.talk.height : 30) + 'px', */
				'border-color': (this.talk.track && this.talk.track.color) ? this.talk.track.color : 'inherit',
			}
		},
		isActive () {
			const now = moment()
			return moment(this.talk.start) > now && moment(this.talk.end) < now
		},
		isBreak () {
			return !this.talk.slug
		},
		timeDisplay () {
			return moment(this.talk.start).format('LT') + ' - ' + moment(this.talk.end).format('LT')
		}
	},
}
</script>
<style lang="stylus">
.pretalx-schedule-talk
	border: 1px solid lighten($clr-primary, 25%)
	border-left: 4px solid lighten($clr-primary, 25%)
	background-color: rgba(255, 255, 255, 0.76)
	box-sizing: border-box
	color: rgba(0, 0, 0, 0.87)
	display: block
	padding: 5px 10px
	padding-top: 0
	position: absolute
	margin: 0 8px
	min-height: 30px
	width: calc(100% - 16px)
	top: calc(var(--start-minutes) * var(--pixels-per-minute) * 1px)
	height: calc(var(--duration-minutes) * var(--pixels-per-minute) * 1px)
	&.break
		cursor: default

	&:hover .popover
		display: block

	.pretalx-schedule-talk-content
		height: 100%
		overflow: hidden

		.do-not-record
			color: rgba(180, 20, 23, 0.87)

		.pretalx-schedule-talk-title
			line-height: 26px
			font-weight: bold

		.pretalx-schedule-talk-speakers
			line-height: 26px

	&.accepted
		background-image: repeating-linear-gradient(
			135deg,
			$gray-lighter,
			$gray-lighter 10px,
			white 10px,
			white 20px
		)

	&:hover
		background-color: $gray-200
		// height: auto !important
		z-index: 6
		box-shadow: 0 3px 3px 0 rgba(0, 0, 0, 0.16),
			0 5px 8px 0 rgba(0, 0, 0, 0.12)

		&::before
			position: absolute
			background-color: $brand-primary
			border-radius: 2px
			color: rgba(255, 255, 255, 0.87)
			content: attr(data-time)
			font-weight: bold
			line-height: 1
			padding: 8px 16px
			top: -44px
			white-space: nowrap

		&::after
			position: absolute
			content: ""
			left: 24px
			width: 0
			height: 0
			border-left: 8px solid transparent
			border-right: 8px solid transparent
			border-top: 8px solid $brand-primary
			top: -14px

.pretalx-schedule-talk.talk-personal,
.pretalx-schedule-talk.active
	background-color: rgba(155, 255, 155, 0.76)

.pretalx-schedule-talk.search-fail
	color: $gray-light
	border-color: $gray-light

.pretalx-schedule-talk.break
	margin: 0
	width: 100%
	background-color: $gray-lightest
	color: $gray
	border: 0
	display: flex
	align-items: center
	flex-grow: 1
	.pretalx-schedule-talk-content
		display: flex
		align-items: center
		flex-grow: 1
	.pretalx-schedule-break-title
		width: 100%
		text-align: center
		text-transform: uppercase
		display: inline-block
		font-weight: bold
		font-size: 16px
	&:hover
		box-shadow: none
		height: auto !important

</style>

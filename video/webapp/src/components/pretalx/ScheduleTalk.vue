<template lang="pug">
a.pretalx-schedule-talk(
	:class="{active: isActive, break: isBreak}"
	:id="'pretalx-' + talk.code || 'break'"
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
		span.pretalx-schedule-talk-speakers(v-if="talk.display_speaker_names")
			|
			| ({{ talk.display_speaker_names }})
		br
</template>
<script>
import { mapState } from 'vuex'
import moment from 'moment'

export default {
	name: 'pretalx-schedule-talk',
	props: {
		talk: Object,
		startOfDay: Object
	},
	computed: {
		...mapState(['world', 'schedule']), // TODO leaky
		track () {
			return this.schedule.event.tracks.find(track => track.name === this.talk.track)
		},
		talkUrl () {
			if (this.isBreak) {
				return null;
			}
			return this.talk.code ? (this.world.pretalx.base_url + 'talk/' + this.talk.code) : '#'
		},
		startMinutes () {
			return moment(this.talk.start).diff(this.startOfDay, 'minutes')
		},
		durationMinutes () {
			return moment(this.talk.end).diff(this.talk.start, 'minutes')
		},
		style () {
			return {
				'--start-minutes': this.startMinutes,
				'--duration-minutes': this.durationMinutes,
				'--track-color': this.track?.color,
				/* 'min-height': (this.talk.height >= 30 ? this.talk.height : 30) + 'px', */
			}
		},
		isActive () {
			const now = moment()
			return moment(this.talk.start) > now && moment(this.talk.end) < now
		},
		isBreak () {
			return !this.talk.code
		},
		timeDisplay () {
			return moment(this.talk.start).format('LT') + ' - ' + moment(this.talk.end).format('LT')
		}
	},
}
</script>
<style lang="stylus">
.pretalx-schedule-talk
	border: 2px solid lighten($clr-primary, 25%)
	border-left: 12px solid lighten($clr-primary, 25%)
	background-color: rgba(255, 255, 255, 0.76)
	box-sizing: border-box
	color: rgba(0, 0, 0, 0.87)
	padding: 0 10px 5px 10px
	position: absolute
	min-height: 30px
	width: calc(100% - 8px)
	top: calc(var(--start-minutes) * var(--pixels-per-minute) * 1px)
	height: calc(var(--duration-minutes) * var(--pixels-per-minute) * 1px)
	border-color: var(--track-color)
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

.pretalx-schedule-talk.break
	margin: 0
	width: 100%
	background-color: $clr-grey-200
	color: $clr-grey
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
		// height: auto !important

</style>

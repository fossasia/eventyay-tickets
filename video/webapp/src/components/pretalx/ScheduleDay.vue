<template lang="pug">
section.pretalx-schedule-day-wrapper(v-scrollbar.y)
	.pretalx-schedule-day(:data-start="day.display_start")
		.pretalx-schedule-day-header-row
			span.pretalx-schedule-time-column.pretalx-schedule-day-header
			.pretalx-schedule-day-room-header(v-for="room in day.rooms", :key="room.name")
				router-link(:to="roomLink(room.id)", v-if="roomLink(room.id)") {{ room.name }}
				span(v-else) {{ room.name }}
		.pretalx-schedule-rooms
			.pretalx-schedule-nowline(:style="nowlineStyle")
			.pretalx-schedule-time-column
				.pretalx-schedule-hour(v-for="hour in hours") {{ hour }}:00
			pretalx-schedule-room(v-for="room in day.rooms", :room="room", :startOfDay="startOfDay", :key="room.name")
</template>
<script>
import moment from 'lib/timetravelMoment'
import range from 'lodash/range'
import last from 'lodash/last'
import PretalxScheduleRoom from './ScheduleRoom'
import {mapState} from 'vuex';

export default {
	name: 'pretalx-schedule-day',
	components: { PretalxScheduleRoom },
	props: {
		day: Object
	},
	methods: {
		roomLink (pretalxId) {
			const room = this.rooms.find((r) => r.pretalx_id === pretalxId)
			if (room) {
				return {
					name: 'room',
					params: {roomId: room.id}
				}
			}
		}
	},
	computed: {
		...mapState(['rooms']),
		startOfDay () {
			let startOfDay
			for (const room of this.day.rooms) {
				if (room.talks.length < 1) continue
				if (!startOfDay || startOfDay.diff(room.talks[0].start) > 0) {
					startOfDay = moment(room.talks[0].start)
				}
			}
			return startOfDay || moment(this.day.start)
		},
		endOfDay () {
			let endOfDay
			for (const room of this.day.rooms) {
				if (room.talks.length < 1) continue
				const lastDate = moment(last(room.talks).end)
				if (!endOfDay || endOfDay.diff(lastDate) < 0) {
					endOfDay = lastDate
				}
			}
			return endOfDay || moment(this.day.end)
		},
		hours () {
			// TODO handle days going over calendar day threshold
			const firstHour = this.startOfDay.get('hour')
			const lastHour = this.endOfDay.get('hour') + 1 // TODO properly check for partially scheduled hours
			return range(firstHour, lastHour)
		},
		nowlineStyle () {
			const now = moment()
			const start = moment(this.day.display_start)
			const end = moment(this.day.end)
			if ((now < end) && (now > start)) {
				const diffSeconds = now.diff(start, 'seconds')
				const diffPx = (diffSeconds / 60 / 60) * 120
				return {top: diffPx + 'px', visibility: 'visisble'}
			}
			return null
		},
	}
}
</script>
<style lang="stylus">
.pretalx-schedule-day
	background: $gray-lightest
	margin-bottom: 16px
	// overflow-y: hidden /* This hides the .nowline element. */
	// overflow-x: auto
	// scroll-snap-type: x mandatory
	// -webkit-scroll-snap-type: x mandatory /* Safari/MacOS in general */
	// -webkit-overflow-scrolling: touch /* Safari/MacOS in general */

	.pretalx-schedule-day-header-row
		background: $gray-lightest
		display: flex
		flex-direction: row
		font-weight: 400

		.pretalx-schedule-day-header
			border-bottom: 4px solid var(--clr-primary)
			background: inherit

		.pretalx-schedule-day-room-header
			border-left: 2px solid lighten($clr-grey-800, 55%)
			border-bottom: 4px solid var(--clr-primary)
			flex: 1 0
			font-size: 20px
			text-align: center
			padding: 8px 0
			overflow-wrap: break-word
			overflow: hidden
			min-width: 150px

	.pretalx-schedule-time-column
		flex: 0 0 4em
		position: sticky
		left: 0px
		z-index: 40
		border-right: 2px solid lighten($clr-grey-800, 55%)

		.pretalx-schedule-hour
			height: calc(60px * var(--pixels-per-minute))
			line-height: 30px
			padding-right: 8px
			text-align: right

		background: repeating-linear-gradient(
			to bottom,
			$clr-grey-200,
			$clr-grey-200 2px,
			$clr-white 2px,
			$clr-white 30px,
			$clr-grey-200 30px,
			$clr-grey-200 31px,
			$clr-white 31px,
			$clr-white 60px
		)
</style>

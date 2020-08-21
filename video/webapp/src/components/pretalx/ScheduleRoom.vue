<template lang="pug">
.pretalx-schedule-room
	.pretalx-schedule-talk-container
		pretalx-schedule-talk(v-for="talk in room.talks", :talk="talk", :startOfDay="startOfDay", :key="talk.code")
</template>
<script>
import PretalxScheduleTalk from './ScheduleTalk'

export default {
	name: 'PretalxScheduleRoom',
	components: { PretalxScheduleTalk },
	props: {
		room: Object,
		startOfDay: Object
	},
	computed: {
	}
}
</script>
<style lang="stylus">
.pretalx-schedule-rooms, .pretalx-schedule-day-header-row
	min-width: min-content

.pretalx-schedule-rooms
	display: flex
	flex-direction: row
	position: relative

	.pretalx-schedule-nowline
		position: absolute
		width: 100%

	.pretalx-schedule-room
		border-left: 2px solid #ccc
		flex: 1 0
		min-width: 150px
		scroll-snap-align: none center
		-webkit-scroll-snap-coordinate: 50% 0% /* older (Safari) */
		scroll-snap-stop: always
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

		.pretalx-schedule-talk-container
			position: relative
</style>

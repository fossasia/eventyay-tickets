<template lang="pug">
.c-schedule
	template(v-if="schedule")
		//- .timezone-control
		//- 	p timezone:
		//- 	timezone-changer
		bunt-tabs.days(v-if="days && days.length > 1", :active-tab="currentDay.toISOString()", ref="tabs", v-scrollbar.x="")
			bunt-tab(v-for="day in days", :id="day.toISOString()", :header="moment(day).format('dddd DD. MMMM')", @selected="changeDay(day)")
		.scroll-parent(ref="scrollParent", v-scrollbar.x.y="")
			grid-schedule(v-if="$mq.above['m']",
				:sessions="sessions",
				:rooms="schedule.rooms",
				:currentDay="currentDay",
				:now="now",
				:scrollParent="$refs.scrollParent",
				:favs="favs",
				@changeDay="currentDay = $event",
				@fav="$store.dispatch('schedule/fav', $event)",
				@unfav="$store.dispatch('schedule/unfav', $event)"
			)
			linear-schedule(v-else,
				:sessions="sessions",
				:rooms="schedule.rooms",
				:currentDay="currentDay",
				:now="now",
				:scrollParent="$refs.scrollParent",
				:favs="favs",
				@changeDay="changeDayByScroll",
				@fav="$store.dispatch('schedule/fav', $event)",
				@unfav="$store.dispatch('schedule/unfav', $event)"
			)
	.error(v-else-if="errorLoading")
		.mdi.mdi-alert-octagon
		h1 {{ $t('schedule/index:scheduleLoadingError') }}
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import { LinearSchedule, GridSchedule} from '@pretalx/schedule'
import moment from 'lib/timetravelMoment'
import TimezoneChanger from 'components/TimezoneChanger'
import scheduleProvidesMixin from 'components/mixins/schedule-provides'

export default {
	components: { LinearSchedule, GridSchedule, TimezoneChanger },
	mixins: [scheduleProvidesMixin],
	data () {
		return {
			moment,
			currentDay: moment().startOf('day')
		}
	},
	computed: {
		...mapState(['now']),
		...mapState('schedule', ['schedule', 'errorLoading']),
		...mapGetters('schedule', ['days', 'sessions', 'favs']),
	},
	methods: {
		changeDay (day) {
			if (day.isSame(this.currentDay)) return
			this.currentDay = day
		},
		changeDayByScroll (day) {
			this.currentDay = day
			const tabEl = this.$refs.tabs.$refs.tabElements.find(el => el.id === day.toISOString())
			// TODO smooth scroll, seems to not work with chrome {behavior: 'smooth', block: 'center', inline: 'center'}
			tabEl?.$el.scrollIntoView()
		}
	}
}
</script>
<style lang="stylus">
.c-schedule
	display: flex
	flex-direction: column
	min-height: 0
	min-width: 0
	.days
		background-color: $clr-white
		tabs-style(active-color: var(--clr-primary), indicator-color: var(--clr-primary), background-color: transparent)
		margin-bottom: 0
		flex: none
		min-width: 0
		.bunt-tabs-header
			min-width: min-content
		.bunt-tabs-header-items
			justify-content: center
			min-width: min-content
			.bunt-tab-header-item
				min-width: min-content
			.bunt-tab-header-item-text
				white-space: nowrap
		.bunt-scrollbar-rail-wrapper-x
			+below('m')
				display: none
	.error
		flex: auto
		display: flex
		flex-direction: column
		justify-content: center
		align-items: center
		.mdi
			font-size: 10vw
			color: $clr-danger
		h1
			font-size: 3vw
			text-align: center
	.c-grid-schedule .grid > .room
		top: 0
	.bunt-scrollbar-rail-wrapper-x, .bunt-scrollbar-rail-wrapper-y
		z-index: 20
</style>

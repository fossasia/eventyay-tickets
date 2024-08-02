<template lang="pug">
.c-schedule
	template(v-if="schedule")
		//- .timezone-control
		//- 	p timezone:
		//- 	timezone-changer
		div.filter-actions
			bunt-button.bunt-ripple-ink(@click="open=true",
				icon="filter-outline"
				:class="{active: filter.type === 'track'}" ) {{ $t('Filter') }}
			bunt-button.bunt-ripple-ink(v-if="favs",
				icon="star"
				@click="toggleFavFilter"
				:class="{active: filter.type === 'fav'}") {{favs.length}}
		bunt-tabs.days(v-if="days && days.length > 1", :active-tab="currentDay.toISOString()", ref="tabs", v-scrollbar.x="")
			bunt-tab(v-for="day in days", :id="day.toISOString()", :header="moment(day).format('dddd DD. MMMM')", @selected="changeDay(day)")
		.scroll-parent(ref="scrollParent", v-scrollbar.x.y="")
			grid-schedule(v-if="$mq.above['m']",
				:sessions="sessions",
				:rooms="rooms",
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
				:rooms="rooms",
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
	prompt.c-filter-prompt(v-if="open", @close="open=false", name="filter-prompt")
		.prompt-content
			h1 {{ $t('Tracks')}}
			template(v-for="track in schedule.tracks")
				div.item(v-if="track")
					bunt-checkbox(v-model="tracksFilter[track.id]",name="track_room_views") {{track.name}}
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import { LinearSchedule, GridSchedule} from '@pretalx/schedule'
import moment from 'lib/timetravelMoment'
import TimezoneChanger from 'components/TimezoneChanger'
import scheduleProvidesMixin from 'components/mixins/schedule-provides'
import Prompt from 'components/Prompt'

export default {
	components: { LinearSchedule, GridSchedule, TimezoneChanger, Prompt },
	mixins: [scheduleProvidesMixin],
	data () {
		return {
			tracksFilter: {},
			open: false,
			moment,
			currentDay: moment().startOf('day')
		}
	},
	computed: {
		...mapState(['now']),
		...mapState('schedule', ['schedule', 'errorLoading', 'filter']),
		...mapGetters('schedule', ['days', 'rooms', 'sessions', 'favs']),
	},
	watch: {
		tracksFilter: {
			handler: function (newValue) {
				if (!this.open) return
				const arr = Object.keys(newValue).filter(key => newValue[key])
				this.$store.dispatch('schedule/filter', {type: 'track', tracks: arr})
			},
			deep: true
		}
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
		},
		toggleFavFilter () {
			this.tracksFilter = {}
			if (this.filter.type === 'fav') {
				this.$store.dispatch('schedule/filter', {})
			} else {
				this.$store.dispatch('schedule/filter', {type: 'fav'})
			}
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
	.scroll-parent
		.bunt-scrollbar-rail-wrapper-x, .bunt-scrollbar-rail-wrapper-y
			z-index: 30
	.c-filter-prompt
		.bunt-scrollbar
			border-radius: 30px
		.prompt-content
			padding: 16px
			display: flex
			flex-direction: column
			.item
				margin: 4px 0px
	.bunt-ripple-ink
		width: fit-content
		padding: 0px 16px
		border-radius: 2px
		height: 32px
		margin: 16px 8px
		&.active
			border: 2px solid #f9a557
</style>

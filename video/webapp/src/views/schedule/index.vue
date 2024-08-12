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
			.export.dropdown
				bunt-progress-circular.export-spinner(v-if="isExporting", size="small")
				custom-dropdown(name="calendar-add1"
					v-model="selectedExporter"
					:options="exportType"
					label="Add to Calendar"
					@input="makeExport")
				
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
					bunt-checkbox(v-model="tracksFilter[track.id]",name="track_room_views") {{ getTrackName(track) }}
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import LinearSchedule from 'views/schedule/schedule-components/LinearSchedule'
import GridSchedule from 'views/schedule/schedule-components/GridSchedule'
import moment from 'lib/timetravelMoment'
import TimezoneChanger from 'components/TimezoneChanger'
import scheduleProvidesMixin from 'components/mixins/schedule-provides'
import Prompt from 'components/Prompt'
import api from 'lib/api'
import config from 'config'
import CustomDropdown from 'views/schedule/export-select'

const exportTypeSet = [
	{
		"id": "ics",
		"label": "Session ICal"
	},
	{
		"id": "json",
		"label": "Session JSON"
	},
	{
		"id": "xcal",
		"label": "Session XCal"
	},
	{
		"id": "xml",
		"label": "Session XML"
	},
	{
		"id": "myics",
		"label": "My ⭐ Sessions ICal"
	},
	{
		"id": "myjson",
		"label": "My ⭐ Sessions JSON"
	},
	{
		"id": "myxcal",
		"label": "My ⭐ Sessions XCal"
	},
	{
		"id": "myxml",
		"label": "My ⭐ Sessions XML"
	},
]

export default {
	components: { LinearSchedule, GridSchedule, TimezoneChanger, Prompt, CustomDropdown },
	mixins: [scheduleProvidesMixin],
	data () {
		return {
			tracksFilter: {},
			open: false,
			moment,
			currentDay: moment().startOf('day'),
			selectedExporter: null,
			exportOptions: [],
			isExporting: false,
			error: null
		}
	},
	computed: {
		...mapState(['now']),
		...mapState('schedule', ['schedule', 'errorLoading', 'filter']),
		...mapGetters('schedule', ['days', 'rooms', 'sessions', 'favs']),
		exportType () {
			return exportTypeSet
		}
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
		getTrackName(track) {
			const language_track = localStorage.userLanguage;
			if (typeof track.name === 'object' && track.name !== null) {
				if (language_track && track.name[language_track]) {
					return track.name[language_track];
				} else {
					return track.name.en || track.name;
				}
			} else {
				return track.name;
			}
		},
		toggleFavFilter () {
			this.tracksFilter = {}
			if (this.filter.type === 'fav') {
				this.$store.dispatch('schedule/filter', {})
			} else {
				this.$store.dispatch('schedule/filter', {type: 'fav'})
			}
		},
		async makeExport() {
			try {
				this.isExporting = true;
				const url = config.api.base + 'export-talk?export_type=' + this.selectedExporter.id
				const authHeader = api._config.token ? `Bearer ${api._config.token}` : (api._config.clientId ? `Client ${api._config.clientId}` : null)
				const result = await fetch(url, {
							method: 'GET',
							headers: {
								Accept: 'application/json',
								Authorization: authHeader,
							}
						}).then(response => response.json())
				var a = document.createElement("a");
				document.body.appendChild(a);
				const blob = new Blob([result], {type: "octet/stream"}),
				download_url = window.URL.createObjectURL(blob);
				a.href = download_url;
				a.download = "schedule-" + this.selectedExporter.id + '.' + this.selectedExporter.id.replace('my','');
				a.click();
				window.URL.revokeObjectURL(download_url);
				a.remove()
				this.isExporting = false;
			} catch (error) {
				this.isExporting = false;
				this.error = error
				console.log(error)
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
	.filter-actions
		display: flex
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
	.export.dropdown
		display: flex
		margin-left: auto
		padding-right: 40px !important
		.bunt-progress-circular
			width: 20px
			height: 20px
		.export-spinner
			padding-top: 22px !important
			margin-right: 10px

</style>

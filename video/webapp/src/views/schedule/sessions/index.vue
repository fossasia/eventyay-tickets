<template lang="pug">
.c-schedule
	template(v-if="schedule")
		div.filter-actions
			app-dropdown(v-for="item in filter", :key="item.refKey", className="schedule")
				template(#toggler)
					span {{item.title}}
					app-dropdown-content(className="schedule")
						app-dropdown-item(v-for="track in item.data", :key="track.value")
							.checkbox-line(:style="{'--track-color': track.color}")
								bunt-checkbox.checkbox-text(type="checkbox", :label="track.label", name="track_room_views", v-model="track.selected", :value="track.value") {{ getTrackName(track) }}
			bunt-button.bunt-ripple-ink(v-if="favs",
				icon="star"
				@click="onlyFavs = !onlyFavs; if (onlyFavs) resetFiltered()"
				:class="onlyFavs ? ['active'] : []") {{favs.length}}

			bunt-button.bunt-ripple-ink(@click="resetAllFiltered", icon="filter-off")

			template(v-if="!inEventTimezone")
				bunt-select.timezone-item(name="timezone", :options="[{id: schedule.timezone, label: schedule.timezone}, {id: userTimezone, label: userTimezone}]", v-model="currentTimezone", @blur="saveTimezone")
			template(v-else)
				div.timezone-label.timezone-item.bunt-tab-header-item {{ schedule.timezone }}

			.export.dropdown
				bunt-progress-circular.export-spinner(v-if="isExporting", size="small")
				custom-dropdown(name="calendar-add1"
					v-model="selectedExporter"
					:options="exportType"
					label="Add to Calendar"
					@input="makeExport")

		bunt-tabs.days(v-if="days && days.length > 1", :active-tab="currentDay.toISOString()", ref="tabs", v-scrollbar.x="")
			bunt-tab(v-for="day in days", :key="day.toISOString()", :id="day.toISOString()", :header="moment(day).format('dddd DD. MMMM')", @selected="changeDay(day)")
		.scroll-parent(ref="scrollParent", v-scrollbar.x.y="")
			linear-schedule(:sessions="sessions",
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
</template>
<script>
import _ from 'lodash'
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
import AppDropdown from 'components/AppDropdown.vue'
import AppDropdownContent from 'components/AppDropdownContent.vue'
import AppDropdownItem from 'components/AppDropdownItem.vue'
const exportTypeSet = [
	{
		id: 'ics',
		label: 'Session ICal'
	},
	{
		id: 'json',
		label: 'Session JSON'
	},
	{
		id: 'xcal',
		label: 'Session XCal'
	},
	{
		id: 'xml',
		label: 'Session XML'
	},
	{
		id: 'myics',
		label: 'My ⭐ Sessions ICal'
	},
	{
		id: 'myjson',
		label: 'My ⭐ Sessions JSON'
	},
	{
		id: 'myxcal',
		label: 'My ⭐ Sessions XCal'
	},
	{
		id: 'myxml',
		label: 'My ⭐ Sessions XML'
	},
]

const defaultFilter = {
	tracks: {
		refKey: 'track',
		data: [],
		title: 'Tracks'
	},
	rooms: {
		refKey: 'room',
		data: [],
		title: 'Rooms'
	},
	types: {
		refKey: 'session_type',
		data: [],
		title: 'Types'
	}
}

export default {
	name: 'Schedule',
	components: { LinearSchedule, GridSchedule, TimezoneChanger, Prompt, CustomDropdown, AppDropdown, AppDropdownContent, AppDropdownItem },
	mixins: [scheduleProvidesMixin],
	data() {
		return {
			tracksFilter: {},
			moment,
			currentDay: moment().startOf('day'),
			selectedExporter: null,
			exportOptions: [],
			isExporting: false,
			error: null,
			defaultFilter: defaultFilter,
			onlyFavs: false,
			userTimezone: null,
			currentTimezone: null,
		}
	},
	computed: {
		...mapState(['now']),
		...mapState('schedule', ['schedule', 'errorLoading']),
		...mapGetters('schedule', ['days', 'rooms', 'sessions', 'favs', 'filterSessionTypesByLanguage', 'filterItemsByLanguage', 'filteredSessions']),
		exportType() {
			return exportTypeSet
		},
		filteredTracks() {
			return this.filteredSessions(this.filter)
		},
		tracksLookup() {
			if (!this.schedule) return {}
			return this.schedule.tracks.reduce((acc, t) => { acc[t.id] = t; return acc }, {})
		},
		roomsLookup() {
			if (!this.schedule) return {}
			return this.schedule.rooms.reduce((acc, room) => { acc[room.id] = room; return acc }, {})
		},
		speakersLookup() {
			if (!this.schedule) return {}
			return this.schedule.speakers.reduce((acc, s) => { acc[s.code] = s; return acc }, {})
		},
		sessions() {
			const sessions = []
			const filter = this.filteredTracks
			for (const session of this.schedule.talks.filter(s => s.start)) {
				if (this.onlyFavs && !this.favs.includes(session.code)) continue
				if (filter && !filter.includes(session.id)) continue
				sessions.push({
					id: session.code,
					title: session.title,
					abstract: session.abstract,
					start: moment.tz(session.start, this.currentTimezone),
					end: moment.tz(session.end, this.currentTimezone),
					speakers: session.speakers?.map(s => this.speakersLookup[s]),
					track: this.tracksLookup[session.track],
					room: this.roomsLookup[session.room],
					fav_count: session.fav_count,
					do_not_record: session.do_not_record,
					tags: session.tags,
					session_type: session.session_type
				})
			}
			sessions.sort((a, b) => a.start.diff(b.start))
			return sessions
		},
		rooms() {
			return _.uniqBy(this.sessions, 'room.id').map(s => s.room)
		},
		filter() {
			const filter = this.defaultFilter

			filter.types.data = this.filterSessionTypesByLanguage(this?.schedule?.session_type)
			filter.rooms.data = this.filterItemsByLanguage(this?.schedule?.rooms)
			filter.tracks.data = this.filterItemsByLanguage(this?.schedule?.tracks)
			return filter
		},
		inEventTimezone() {
			if (!this.schedule?.talks?.length) return false
			const example = this.schedule.talks[0].start
			return moment.tz(example, this.userTimezone).format('Z') === moment.tz(example, this.schedule.timezone).format('Z')
		},
	},
	async created() {
		this.userTimezone = moment.tz.guess()
		this.currentTimezone = localStorage.getItem(`userTimezone`)
	},
	watch: {
		tracksFilter: {
			handler: function(newValue) {
				const arr = Object.keys(newValue).filter(key => newValue[key])
				this.$store.dispatch('schedule/filter', {type: 'track', tracks: arr})
				this.onlyFavs = false
			},
			deep: true
		}
	},
	methods: {
		changeDay(day) {
			if (day.isSame(this.currentDay)) return
			this.currentDay = day
		},
		changeDayByScroll(day) {
			this.currentDay = day
			const tabEl = this.$refs.tabs.$refs.tabElements.find(el => el.id === day.toISOString())
			// TODO smooth scroll, seems to not work with chrome {behavior: 'smooth', block: 'center', inline: 'center'}
			tabEl?.$el.scrollIntoView()
		},
		getTrackName(track) {
			const languageUrl = localStorage.userLanguage
			if (typeof track.name === 'object' && track.name !== null) {
				if (languageUrl && track.name[languageUrl]) {
					return track.name[languageUrl]
				} else {
					return track.name.en || track.name
				}
			} else if (track.session_type && track.session_type !== null) {
				return track.session_type
			} else {
				return track.name
			}
		},
		toggleFavFilter() {
			this.tracksFilter = {}
			if (this.filter.type === 'fav') {
				this.$store.dispatch('schedule/filter', {})
			} else {
				this.$store.dispatch('schedule/filter', {type: 'fav'})
			}
		},
		async makeExport() {
			try {
				this.isExporting = true
				const url = config.api.base + 'export-talk?export_type=' + this.selectedExporter.id
				const authHeader = api._config.token ? `Bearer ${api._config.token}` : (api._config.clientId ? `Client ${api._config.clientId}` : null)
				const result = await fetch(url, {
					method: 'GET',
					headers: {
						Accept: 'application/json',
						Authorization: authHeader,
					}
				}).then(response => response.json())
				var a = document.createElement('a')
				document.body.appendChild(a)
				const blob = new Blob([result], {type: 'octet/stream'})
				const downloadUrl = window.URL.createObjectURL(blob)
				a.href = downloadUrl
				a.download = 'schedule-' + this.selectedExporter.id + '.' + this.selectedExporter.id.replace('my', '')
				a.click()
				window.URL.revokeObjectURL(downloadUrl)
				a.remove()
				this.isExporting = false
			} catch (error) {
				this.isExporting = false
				this.error = error
				console.log(error)
			}
		},
		resetAllFiltered() {
			this.resetFiltered()
			this.onlyFavs = false
		},
		resetFiltered() {
			Object.keys(this.filter).forEach(key => {
				this.filter[key].data.forEach(t => {
					if (t.selected) {
						t.selected = false
					}
				})
			})
		},
		resetOnlyFavs() {
			this.onlyFavs = false
		},
		saveTimezone() {
			localStorage.setItem(`userTimezone`, this.currentTimezone)
		},
	}
}
</script>
<style lang="stylus">
@media (max-width: 480px)
    .filter-actions
        flex-direction: column
        .app-drop-down
            width: 90px
            margin-bottom: 8px
    .c-schedule
        .bunt-ripple-ink
            margin: 12px 0 20px 15px !important;
        .export.dropdown
            padding-right: 0
            margin-left: 15px !important

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
        padding-right: 40px
        .bunt-progress-circular
            width: 20px
            height: 20px
        .export-spinner
            padding-top: 22px !important
            margin-right: 10px
	.bunt-select
		.bunt-input
			height: auto !important
</style>

<template lang="pug">
.pretalx-schedule(:style="{'--scrollparent-width': scrollParentWidth + 'px'}", :class="draggedSession ? ['is-dragging'] : []", @pointerup="stopDragging")
	template(v-if="schedule")
		#main-wrapper
			#unassigned.no-print(v-scrollbar.y="", @pointerenter="isUnassigning = true", @pointerleave="isUnassigning = false")
				.title
					bunt-input#filter-input(v-model="unassignedFilterString", :placeholder="$t('Filter sessions')", icon="search")
					#unassigned-sort(@click="showUnassignedSortMenu = !showUnassignedSortMenu", :class="{'active': showUnassignedSortMenu}")
						i.fa.fa-sort
					#unassigned-sort-menu(v-if="showUnassignedSortMenu")
						.sort-method(v-for="method of unassignedSortMethods", @click="unassignedSort === method.name ? unassignedSortDirection = unassignedSortDirection * -1 : unassignedSort = method.name; showUnassignedSortMenu = false")
							span {{ method.label }}
							i.fa.fa-sort-amount-asc(v-if="unassignedSort === method.name && unassignedSortDirection === 1")
							i.fa.fa-sort-amount-desc(v-if="unassignedSort === method.name && unassignedSortDirection === -1")
				session.new-break(:session="{title: '+ ' + $t('New break')}", :isDragged="false", @startDragging="startNewBreak", @click="showNewBreakHint", v-tooltip.fixed="{text: newBreakTooltip, show: newBreakTooltip}", @pointerleave="removeNewBreakHint")
				session(v-for="un in unscheduled", :session="un", @startDragging="startDragging", :isDragged="draggedSession && un.id === draggedSession.id")
			#schedule-wrapper(v-scrollbar.x.y="")
				bunt-tabs.days(v-if="days", :modelValue="currentDay.format()", ref="tabs" :class="['grid-tabs']")
					bunt-tab(v-for="day of days", :id="day.format()", :header="day.format(dateFormat)", @selected="changeDay(day)")
				grid-schedule(:sessions="sessions",
					:rooms="schedule.rooms",
					:availabilities="availabilities",
					:warnings="warnings",
					:start="days[0]",
					:end="days.at(-1).clone().endOf('day')",
					:currentDay="currentDay",
					:draggedSession="draggedSession",
					@changeDay="currentDay = $event",
					@startDragging="startDragging",
					@rescheduleSession="rescheduleSession",
					@createSession="createSession",
					@editSession="editorStart($event)")
			#session-editor-wrapper(v-if="editorSession", @click="editorSession = null")
				form#session-editor(@click.stop="", @submit.prevent="editorSave")
					h3.session-editor-title(v-if="editorSession.code")
						a(v-if="editorSession.code", :href="`/orga/event/${eventSlug}/submissions/${editorSession.code}/`") {{editorSession.title }}
						span(v-else) {{editorSession.title }}
					.data
						.data-row(v-if="editorSession.code")
							.data-label(v-if="editorSession.speakers && editorSession.speakers.length == 1") {{ $t('Speaker') }}
							.data-label(v-else) {{ $t('Speakers') }}
							.data-value
								span(v-for="speaker, index of editorSession.speakers")
									a(:href="`/orga/event/${eventSlug}/speakers/${speaker.code}/`") {{speaker.name}}
									span(v-if="index != editorSession.speakers.length - 1") {{', '}}
						.data-row(v-else).form-group
							.data-label {{ $t('Title') }}
							.data-value.i18n-form-group
								template(v-for="locale of locales")
									input(v-model="editorSession.title[locale]", :required="true" :lang="locale")
						.data-row(v-if="editorSession.track")
							.data-label {{ $t('Track') }}
							.data-value {{ getLocalizedString(editorSession.track.name) }}
						.data-row(v-if="editorSession.room")
							.data-label {{ $t('Room') }}
							.data-value {{ getLocalizedString(editorSession.room.name) }}
						.data-row
							.data-label {{ $t('Duration') }}
							.data-value.number
								input(v-model="editorSession.duration", type="number", min="1", max="1440", step="1", :required="true")
								span {{ $t('minutes') }}

						.data-row(v-if="editorSession.code && warnings[editorSession.code] && warnings[editorSession.code].length")
							.data-label
								i.fa.fa-exclamation-triangle.warning
								span {{ $t('Warnings') }}
							.data-value
								ul(v-if="warnings[editorSession.code].length > 1")
									li.warning(v-for="warning of warnings[editorSession.code]") {{ warning.message }}
								span(v-else) {{ warnings[editorSession.code][0].message }}
					.button-row
						input(type="submit")
						bunt-button#btn-delete(v-if="!editorSession.code", @click="editorDelete", :loading="editorSessionWaiting") {{ $t('Delete') }}
						bunt-button#btn-save(@click="editorSave", :loading="editorSessionWaiting") {{ $t('Save') }}
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import moment from 'moment-timezone'
import Editor from '~/components/Editor'
import GridSchedule from '~/components/GridSchedule'
import Session from '~/components/Session'
import api from '~/api'
import { getLocalizedString } from '~/utils'

export default {
	name: 'PretalxSchedule',
	components: { Editor, GridSchedule, Session },
	props: {
		locale: String,
		version: {
			type: String,
			default: ''
		}
	},
	data () {
		return {
			moment,
			eventSlug: null,
			scrollParentWidth: Infinity,
			schedule: null,
			availabilities: {rooms: {}, talks: {}},
			warnings: {},
			currentDay: null,
			draggedSession: null,
			editorSession: null,
			editorSessionWaiting: false,
			isUnassigning: false,
			locales: ["en"],
			unassignedFilterString: '',
			unassignedSort: 'title',
			unassignedSortDirection: 1,  // asc
			showUnassignedSortMenu: false,
			newBreakTooltip: '',
			getLocalizedString,
		}
	},
	computed: {
		roomsLookup () {
			if (!this.schedule) return {}
			return this.schedule.rooms.reduce((acc, room) => { acc[room.id] = room; return acc }, {})
		},
		tracksLookup () {
			if (!this.schedule) return {}
			return this.schedule.tracks.reduce((acc, t) => { acc[t.id] = t; return acc }, {})
		},
		unassignedSortMethods () {
			const sortMethods = [
				{label: this.$t('Title'), name: 'title'},
				{label: this.$t('Speakers'), name: 'speakers'},
			]
			if (this.schedule && this.schedule.tracks.length > 1) {
				sortMethods.push({label: this.$t('Track'), name: 'track'})
			}
			sortMethods.push({label: this.$t('Duration'), name: 'duration' })
			return sortMethods
		},
		speakersLookup () {
			if (!this.schedule) return {}
			return this.schedule.speakers.reduce((acc, s) => { acc[s.code] = s; return acc }, {})
		},
		unscheduled () {
			if (!this.schedule) return
			let sessions = []
			for (const session of this.schedule.talks.filter(s => !s.start || !s.room)) {
				sessions.push({
					id: session.id,
					code: session.code,
					title: session.title,
					abstract: session.abstract,
					speakers: session.speakers?.map(s => this.speakersLookup[s]),
					track: this.tracksLookup[session.track],
					duration: session.duration,
					state: session.state,
				})
			}
			if (this.unassignedFilterString.length) {
				sessions = sessions.filter(s => {
					const title = getLocalizedString(s.title)
					const speakers = s.speakers?.map(s => s.name).join(', ') || ''
					return title.toLowerCase().includes(this.unassignedFilterString.toLowerCase()) || speakers.toLowerCase().includes(this.unassignedFilterString.toLowerCase())
				})
			}
			// Sort by this.unassignedSort, this.unassignedSortDirection (1 or -1)
			sessions = sessions.sort((a, b) => {
				if (this.unassignedSort == 'title') {
					return getLocalizedString(a.title).toUpperCase().localeCompare(getLocalizedString(b.title).toUpperCase()) * this.unassignedSortDirection
				} else if (this.unassignedSort == 'speakers') {
					const aSpeakers = a.speakers?.map(s => s.name).join(', ') || ''
					const bSpeakers = b.speakers?.map(s => s.name).join(', ') || ''
					return aSpeakers.toUpperCase().localeCompare(bSpeakers.toUpperCase()) * this.unassignedSortDirection
				} else if (this.unassignedSort == 'track') {
					return getLocalizedString(a.track ? a.track.name : '').toUpperCase().localeCompare(getLocalizedString(b.track? b.track.name : '').toUpperCase()) * this.unassignedSortDirection
				} else if (this.unassignedSort == 'duration') {
					return (a.duration - b.duration) * this.unassignedSortDirection
				}
			})
			return sessions
		},
		sessions () {
			if (!this.schedule) return
			const sessions = []
			for (const session of this.schedule.talks.filter(s => s.start && moment(s.start).isAfter(this.days[0]) && moment(s.start).isBefore(this.days.at(-1).clone().endOf('day')))) {
				sessions.push({
					id: session.id,
					code: session.code,
					title: session.title,
					abstract: session.abstract,
					start: moment(session.start),
					end: moment(session.end),
					duration: moment(session.end).diff(session.start, 'm'),
					speakers: session.speakers?.map(s => this.speakersLookup[s]),
					track: this.tracksLookup[session.track],
					state: session.state,
					room: this.roomsLookup[session.room]
				})
			}
			sessions.sort((a, b) => a.start.diff(b.start))
			return sessions
		},
		days () {
			if (!this.schedule) return
			const days = [moment(this.schedule.event_start).startOf('day')]
			const lastDay = moment(this.schedule.event_end)
			while (!days.at(-1).isSame(lastDay, 'day')) {
				days.push(days.at(-1).clone().add(1, 'days'))
			}
			return days
		},
		inEventTimezone () {
			if (!this.schedule || !this.schedule.talks) return false
			const example = this.schedule.talks[0].start
			return moment.tz(example, this.userTimezone).format('Z') === moment.tz(example, this.schedule.timezone).format('Z')
		},
		dateFormat () {
			// Defaults to dddd DD. MMMM for: all grid schedules with more than two rooms, and all list schedules with less than five days
			// After that, we start to shorten the date string, hoping to reduce unwanted scroll behaviour
			if ((this.schedule && this.schedule.rooms.length > 2) || !this.days || !this.days.length) return 'dddd DD. MMMM'
			if (this.days && this.days.length <= 5) return 'dddd DD. MMMM'
			if (this.days && this.days.length <= 7) return 'dddd DD. MMM'
			return 'ddd DD. MMM'
		}
	},
	async created () {
		const version = ''
		this.schedule = await this.fetchSchedule()
		// needs to be as early as possible
		this.eventTimezone = this.schedule.timezone
		moment.tz.setDefault(this.eventTimezone)
		this.locales = this.schedule.locales
		this.eventSlug = window.location.pathname.split("/")[3]
		this.currentDay = this.days[0]
		window.setTimeout(this.pollUpdates, 10 * 1000)
		await this.fetchAdditionalScheduleData()
		await new Promise((resolve) => {
			const poll = () => {
				if (this.$el.parentElement || this.$el.getRootNode().host) return resolve()
				setTimeout(poll, 100)
			}
			poll()
		})
	},
	async mounted () {
		// We block until we have either a regular parent or a shadow DOM parent
		window.addEventListener('resize', this.onWindowResize)
		this.onWindowResize()
	},
	destroyed () {
		// TODO destroy observers
	},
	methods: {
		changeDay (day) {
			if (day.isSame(this.currentDay)) return
			this.currentDay = moment(day, this.eventTimezone).startOf('day')
			window.location.hash = day.format('YYYY-MM-DD')
		},
		saveTalk (session) {
			api.saveTalk(session).then(response => {
				this.warnings[session.code] = response.warnings
				this.schedule.talks.find(s => s.id === session.id).updated = response.updated
			})
		},
		rescheduleSession (e) {
			const movedSession = this.schedule.talks.find(s => s.id === e.session.id)
			this.stopDragging()
			movedSession.start = e.start
			movedSession.end = e.end
			movedSession.room = e.room.id
			this.saveTalk(movedSession)
		},
		createSession (e) {
			api.createTalk(e.session).then(response => {
				this.warnings[e.session.code] = response.warnings
				const newSession = Object.assign({}, e.session)
				newSession.id = response.id
				this.schedule.talks.push(newSession)
				this.editorStart(newSession)
			})
		},
		editorStart (session) {
			this.editorSession = session
		},
		editorSave () {
			this.editorSessionWaiting = true
			this.editorSession.end = moment(this.editorSession.start).clone().add(this.editorSession.duration, 'm')
			this.saveTalk(this.editorSession)

			const session = this.schedule.talks.find(s => s.id === this.editorSession.id)
			session.end = this.editorSession.end
			if (!session.submission) {
				session.title = this.editorSession.title
			}
			this.editorSessionWaiting = false
			this.editorSession = null
		},
		editorDelete () {
			this.editorSessionWaiting = true
			api.deleteTalk(this.editorSession)
			this.schedule.talks = this.schedule.talks.filter(s => s.id !== this.editorSession.id)
			this.editorSessionWaiting = false
			this.editorSession = null
		},
		showNewBreakHint () {
			// Users try to click the "+ New Break" box instead of dragging it to the schedule
			// so we show a hint on-click
			this.newBreakTooltip = this.$t('Drag the box to the schedule to create a new break.')
		},
		removeNewBreakHint () {
			this.newBreakTooltip = ''
		},
		startNewBreak({event}) {
			const title = this.locales.reduce((obj, locale) => {
				obj[locale] = this.$t("New Break")
				return obj
			}, {})
			this.startDragging({event, session: {title, duration: "5", uncreated: true}})
		},
		startDragging ({event, session}) {
			if (this.availabilities && this.availabilities.talks[session.id] && this.availabilities.talks[session.id].length !== 0) {
				session.availabilities = this.availabilities.talks[session.id]
			}
			// TODO: capture the pointer with setPointerCapture(event)
			// This allows us to call stopDragging() even when the mouse is released
			// outside the browser.
			// https://developer.mozilla.org/en-US/docs/Web/API/Element/setPointerCapture
			this.draggedSession = session
		},
		stopDragging (session) {
			try {
				if (this.isUnassigning && this.draggedSession) {
					if (this.draggedSession.code) {
						const movedSession = this.schedule.talks.find(s => s.id === this.draggedSession.id)
						movedSession.start = null
						movedSession.end = null
						movedSession.room = null
						this.saveTalk(movedSession)
					} else if (this.schedule.talks.find(s => s.id === this.draggedSession.id)) {
						this.schedule.talks = this.schedule.talks.filter(s => s.id !== this.draggedSession.id)
						api.deleteTalk(this.draggedSession)
					}
				}
			} finally {
				this.draggedSession = null
				this.isUnassigning = false
			}
		},
		onWindowResize () {
			this.scrollParentWidth = document.body.offsetWidth
		},
		async fetchSchedule(options) {
		  const schedule = await (api.fetchTalks(options))
		  return schedule
		},
		async fetchAdditionalScheduleData() {
			this.availabilities = await api.fetchAvailabilities()
			this.warnings = await api.fetchWarnings()
		},
		async pollUpdates () {
			this.fetchSchedule({since: this.since, warnings: true}).then(schedule => {
				if (schedule.version !== this.schedule.version) {
					// we need to reload if a new schedule version is available
					window.location.reload()
				}
				// For each talk in the schedule, we check if it has changed and if our update date is newer than the last change
				schedule.talks.forEach(talk => {
					const oldTalk = this.schedule.talks.find(t => t.id === talk.id)
					if (!oldTalk) {
						this.schedule.talks.push(talk)
					} else {
						if (moment(talk.updated).isAfter(moment(oldTalk.updated))) {
							Object.assign(oldTalk, talk)
						}
					}
				})
				this.since = schedule.now
				window.setTimeout(this.pollUpdates, 10 * 1000)
			})
		}
	}
}
</script>
<style lang="stylus">
#page-content
	padding: 0
.pretalx-schedule
	display: flex
	flex-direction: column
	min-height: 0
	min-width: 0
	height: calc(100vh - 160px)
	width: 100%
	font-size: 14px
	margin-left: 24px
	font-family: inherit
	h1, h2, h3, h4, h5, h6, legend, button, .btn
		font-family: "Titillium Web", "Open Sans", "OpenSans", "Helvetica Neue", Helvetica, Arial, sans-serif
	&.is-dragging
		user-select: none
		cursor: grabbing
	#main-wrapper
		display: flex
		flex: auto
		min-height: 0
		min-width: 0
	.settings
		margin-left: 18px
		align-self: flex-start
		display: flex
		align-items: center
		position: sticky
		z-index: 100
		left: 18px
		.bunt-select
			max-width: 300px
			padding-right: 8px
		.timezone-label
			cursor: default
			color: $clr-secondary-text-light
	.days
		background-color: $clr-white
		tabs-style(active-color: var(--pretalx-clr-primary), indicator-color: var(--pretalx-clr-primary), background-color: transparent)
		overflow-x: auto
		position: sticky
		left: 0
		top: 0
		margin-bottom: 0
		flex: none
		min-width: 0
		height: 48px
		z-index: 30
		.bunt-tabs-header
			min-width: min-content
		.bunt-tabs-header-items
			justify-content: center
			min-width: min-content
			.bunt-tab-header-item
				min-width: min-content
			.bunt-tab-header-item-text
				white-space: nowrap
	#unassigned
		margin-top: 35px
		width: 350px
		flex: none
		> *
			margin-right: 12px
		> .bunt-scrollbar-rail-y
			margin: 0
		> .title
			padding 4px 0
			font-size: 18px
			text-align: center
			background-color: $clr-white
			border-bottom: 4px solid $clr-dividers-light
			display: flex
			align-items: flex-end
			margin-left: 8px
			#filter-input
				width: calc(100% - 36px)
			#unassigned-sort
				width: 28px
				height: 28px
				text-align: center
				cursor: pointer
				border-radius: 4px
				margin-bottom: 8px
				margin-left: 4px
				color: $clr-secondary-text-light
				&:hover, &.active
					opacity: 0.8
					background-color: $clr-dividers-light
		.new-break.c-linear-schedule-session
			min-height: 48px
		#unassigned-sort-menu
			color: $clr-primary-text-light
			display: flex
			flex-direction: column
			background-color: white
			position: absolute
			top: 53px
			right: 15px
			width: 130px
			font-size: 16px
			cursor: pointer
			z-index: 1000
			box-shadow: 0 2px 4px rgba(0, 0, 0, 0.5)
			text-align: left;
			.sort-method
				padding: 8px 16px
				display: flex
				justify-content: space-between
				align-items: center
				&:hover
					background-color: $clr-dividers-light
	#schedule-wrapper
		width: 100%
		margin-right: 40px
  #session-editor-wrapper
		position: absolute
		z-index: 1000
		top: 0
		left: 0
		width: 100%
		height: 100%
		background-color: rgba(0, 0, 0, 0.5)

		#session-editor
			background-color: $clr-white
			border-radius: 4px
			padding: 32px 40px
			position: absolute
			top: 50%
			left: 50%
			transform: translate(-50%, -50%)
			width: 680px

			.session-editor-title
				font-size: 22px
				margin-bottom: 16px
			.button-row
				display: flex
				width: 100%
				margin-top: 24px

				.bunt-button-content
					font-size: 16px !important
				#btn-delete
					button-style(color: $clr-danger, text-color: $clr-white)
					font-weight: bold;
				#btn-save
					margin-left: auto
					font-weight: bold;
					button-style(color: #3aa57c)
				[type=submit]
					display: none
			.data
				display: flex
				flex-direction: column
				font-size: 16px
				.data-row
					display: flex
					margin: 4px 0
					.data-label
						width: 130px
						font-weight: bold
						display: flex
						align-items: baseline
					.data-value
						input
							border: 1px solid #ced4da
							width: 100%
							border-radius: 0.25rem
							font-size: 16px
							height: 30px
							&:focus, &:active, &:focus-visible
								border-color: #89d6b8
								box-shadow: 0 0 0 1px rgba(58, 165, 124, 0.25)
							&[type=number]
								width: 60px
								text-align: right
								padding-right: 8px
								margin-right: 8px
						ul
							list-style: none
							padding: 0
		.warning
			color: #b23e65
</style>

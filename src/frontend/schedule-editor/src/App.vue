<template lang="pug">
.pretalx-schedule(:style="{'--scrollparent-width': scrollParentWidth + 'px'}", :class="draggedSession ? ['is-dragging'] : []", @pointerup="stopDragging")
	template(v-if="schedule")
		#main-wrapper
			#unassigned(v-scrollbar.y="", @pointerenter="isUnassigning = true", @pointerleave="isUnassigning = false")
				.title {{$t('Unassigned')}}
				session(:session="{title: '+ ' + $t('New break')}", :isDragged="false", @startDragging="startNewBreak")
				session(v-for="un in unscheduled", :session="un", @startDragging="startDragging", :isDragged="draggedSession && un.id === draggedSession.id")
			#schedule-wrapper(v-scrollbar.x.y="")
				bunt-tabs.days(v-if="days", :active-tab="currentDay && currentDay.format()", ref="tabs" :class="['grid-tabs']")
					bunt-tab(v-for="day of days", :id="day.format()", :header="day.format(dateFormat)", @selected="changeDay(day)")
				grid-schedule(:sessions="sessions",
					:rooms="schedule.rooms",
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
					h3.session-editor-title(v-if="editorSession.code") {{editorSession.title }}
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
			currentDay: null,
			draggedSession: null,
			editorSession: null,
			editorSessionWaiting: false,
			isUnassigning: false,
			locales: ["en"],
			getLocalizedString
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
		speakersLookup () {
			if (!this.schedule) return {}
			return this.schedule.speakers.reduce((acc, s) => { acc[s.code] = s; return acc }, {})
		},
		unscheduled () {
			if (!this.schedule) return
			const sessions = []
			for (const session of this.schedule.talks.filter(s => !s.start || !s.room)) {
				sessions.push({
					id: session.id,
					code: session.code,
					title: session.title,
					abstract: session.abstract,
					speakers: session.speakers?.map(s => this.speakersLookup[s]),
					track: this.tracksLookup[session.track],
					duration: session.duration,
				})
			}
			sessions.sort((a, b) => getLocalizedString(a.title).toUpperCase().localeCompare(getLocalizedString(b.title).toUpperCase()))
			return sessions
		},
		newBreakTitle () {
			const title = {"en": "New break"}
			for (const locale of this.locales.filter(l => l != "en")) {
				title[locale] = this.$t('New break')
			}
			return title
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
		moment.locale(this.locale)
		const version = ''
		this.schedule = await this.fetchSchedule()
		this.currentDay = this.days[0]
		this.eventTimezone = this.schedule.timezone
		this.locales = this.schedule.locales
		this.eventSlug = window.location.pathname.split("/")[3]
		moment.tz.setDefault(this.eventTimezone)
		window.setTimeout(this.pollUpdates, 10 * 1000)
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
		rescheduleSession (e) {
			const movedSession = this.schedule.talks.find(s => s.id === e.session.id)
			this.stopDragging()
			movedSession.start = e.start
			movedSession.end = e.end
			movedSession.room = e.room.id
			api.saveTalk(movedSession)
			// TODO show the resulting warnings in response.warnings
		},
		createSession (e) {
			this.schedule.talks.push(e.session)
			api.createTalk(e.session)
			this.editorStart(e.session)
			// TODO show the resulting warnings in response.warnings
		},
		editorStart (session) {
			this.editorSession = session
		},
		editorSave () {
			this.editorSessionWaiting = true
			this.editorSession.end = moment(this.editorSession.start).clone().add(this.editorSession.duration, 'm')
			api.saveTalk(this.editorSession)

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
		startNewBreak({event}) {
		  this.startDragging({event, session: {title: this.newBreakTitle, duration: "30", uncreated: true}})
		},
		startDragging ({event, session}) {
			this.draggedSession = session
			// TODO: capture the pointer with setPointerCapture(event)
			// This allows us to call stopDragging() even when the mouse is released
			// outside the browser.
			// https://developer.mozilla.org/en-US/docs/Web/API/Element/setPointerCapture
		},
		stopDragging (session) {
			try {
				if (this.isUnassigning && this.draggedSession) {
					if (this.draggedSession.code) {
						const movedSession = this.schedule.talks.find(s => s.id === this.draggedSession.id)
						movedSession.start = null
						movedSession.end = null
						movedSession.room = null
						api.saveTalk(movedSession)
					} else {
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
		  const apiRooms = (await api.fetchRooms()).results.reduce((acc, room) => {
			  acc[room.id] = room
			  return acc
		  }, {})
		  schedule.rooms = schedule.rooms.map(room => apiRooms[room.id])
		  return schedule
		},
		async pollUpdates () {
			//this.schedule = await this.fetchSchedule({since: this.since, warnings: true})
			//window.setTimeout(this.pollUpdates, 10 * 1000)
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
		margin-top: 64px
		width: 350px
		flex: none
		> .title
			margin 0 8px
			padding 4px 0
			font-size: 18px
			text-align: center
			background-color: $clr-white
			border-bottom: 4px solid $clr-dividers-light
	#schedule-wrapper
		width: 100%
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
</style>

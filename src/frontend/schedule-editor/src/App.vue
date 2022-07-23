<template lang="pug">
.pretalx-schedule(:style="{'--scrollparent-width': scrollParentWidth + 'px'}", :class="draggedSession ? ['is-dragging'] : []", @mouseup="stopDragging")
	template(v-if="schedule")
		.settings
			template(v-if="!inEventTimezone")
				bunt-select(name="timezone", :options="[{id: schedule.timezone, label: schedule.timezone}, {id: userTimezone, label: userTimezone}]", v-model="currentTimezone", @blur="saveTimezone")
			template(v-else)
				div.timezone-label.bunt-tab-header-item(v-html="schedule.timezone")
		#main-wrapper
			#unassigned(v-scrollbar.y="", @mouseenter="isUnassigning = true", @mouseLeave="isUnassigning = false")
				h1 Unassigned
				session(v-for="un in unscheduled", :session="un", :showAbstract="false", @startDragging="startDragging(un)", :isDragged="draggedSession && un.id === draggedSession.id")
			#schedule-wrapper(v-scrollbar.x.y="")
				bunt-tabs.days(v-if="days && days.length > 1", :active-tab="currentDay && currentDay.format()", ref="tabs" :class="['grid-tabs']")
					bunt-tab(v-for="day in days", :id="day.format()", :header="day.format(dateFormat)", @selected="changeDay(day)")
				grid-schedule(:sessions="sessions",
					:rooms="schedule.rooms",
					:currentDay="currentDay",
					:draggedSession="draggedSession",
					@changeDay="currentDay = $event",
					@startDragging="startDragging($event)",
					@rescheduleSession="rescheduleSession($event)")
			editor(v-scrollbar.y="", :session="editorSession")
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import moment from 'moment-timezone'
import Editor from '~/components/Editor'
import GridSchedule from '~/components/GridSchedule'
import Session from '~/components/Session'
import api from '~/api'

export default {
	name: 'PretalxSchedule',
	components: { Editor, GridSchedule, Session },
	props: {
		eventUrl: String,
		apiToken: String,
		locale: String,
		version: {
			type: String,
			default: ''
		}
	},
	provide () {
		return {
			eventUrl: this.eventUrl
		}
	},
	data () {
		return {
			moment,
			scrollParentWidth: Infinity,
			schedule: null,
			userTimezone: null,
			currentDay: null,
			currentTimezone: null,
			draggedSession: null,
			editorSession: null,
			isUnassigning: false,
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
			if (!this.schedule || !this.currentTimezone) return
			const sessions = []
			for (const session of this.schedule.talks.filter(s => !s.start || !s.room)) {
				sessions.push({
					id: session.code,
					title: session.title,
					abstract: session.abstract,
					speakers: session.speakers?.map(s => this.speakersLookup[s]),
					track: this.tracksLookup[session.track],
					duration: session.duration,
				})
			}
			sessions.sort((a, b) => a.title.toUpperCase() > b.title.toUpperCase())
			return sessions
		},
		sessions () {
			if (!this.schedule || !this.currentTimezone) return
			const sessions = []
			for (const session of this.schedule.talks.filter(s => s.start && moment(s.start).isAfter(this.days[0]) && moment(s.start).isBefore(this.days.at(-1).clone().endOf('day')))) {
				sessions.push({
					id: session.code,
					title: session.title,
					abstract: session.abstract,
					start: moment.tz(session.start, this.currentTimezone),
					end: moment.tz(session.end, this.currentTimezone),
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
		},
		eventSlug () {
			let url = ''
			if (this.eventUrl.startsWith('http')) {
				url = new URL(this.eventUrl)
			} else {
				url = new URL('http://example.org/' + this.eventUrl)
			}
			return url.pathname.replace(/\//g, '')
		}
	},
	async created () {
		moment.locale(this.locale)
		this.userTimezone = moment.tz.guess()
		const version = ''
		this.schedule = await (api.fetchTalks(this.apiToken, this.eventSlug))
		this.currentTimezone = localStorage.getItem(`${this.eventSlug}_timezone`)
		this.currentTimezone = [this.schedule.timezone, this.userTimezone].includes(this.currentTimezone) ? this.currentTimezone : this.schedule.timezone
		this.currentDay = this.days[0]

		const fragment = window.location.hash.slice(1)
		if (fragment && fragment.length === 10) {
			const initialDay = moment(fragment, 'YYYY-MM-DD')

			const filteredDays = this.days.filter(d => d.format('YYYYMMDD') === initialDay.format('YYYYMMDD'))
			if (filteredDays.length) {
				this.currentDay = filteredDays[0]
			}
		}
		window.setTimeout(this.pollUpdates, 10 * 1000)
	},
	async mounted () {
		// We block until we have either a regular parent or a shadow DOM parent
		await new Promise((resolve) => {
			const poll = () => {
				if (this.$el.parentElement || this.$el.getRootNode().host) return resolve()
				setTimeout(poll, 100)
			}
			poll()
		})
		window.addEventListener('resize', this.onWindowResize)
		this.onWindowResize()
	},
	destroyed () {
		// TODO destroy observers
	},
	methods: {
		changeDay (day) {
			if (day.isSame(this.currentDay)) return
			this.currentDay = moment(day, this.currentTimezone).startOf('day')
			window.location.hash = day.format('YYYY-MM-DD')
		},
		rescheduleSession (e) {
			const movedSession = this.schedule.talks.find(s => s.code === e.session.id)
			this.stopDragging()
			movedSession.start = e.start
			movedSession.end = e.end
			movedSession.room = e.room.id
			// TODO push to server
		},
		startDragging (session) {
			this.draggedSession = session
			this.editorSession = session
		},
		stopDragging (session) {
			if (this.isUnassigning && this.draggedSession) {
				const movedSession = this.schedule.talks.find(s => s.code === this.draggedSession.id)
				movedSession.start = null
				movedSession.end = null
				movedSession.room = null
				// TODO push to server
			}
			this.draggedSession = null
			this.isUnassigning = false
		},
		onWindowResize () {
			this.scrollParentWidth = document.body.offsetWidth
		},
		pollUpdates () {
			api
				.fetchTalks(this.apiToken, this.eventSlug, {since: this.since, warnings: true})
				.then(result => {
					this.schedule = result
					window.setTimeout(this.pollUpdates, 10 * 1000)
				})
		},
		saveTimezone () {
			localStorage.setItem(`${this.eventSlug}_timezone`, this.currentTimezone)
		}
	}
}
</script>
<style lang="stylus">
.pretalx-schedule
	display: flex
	flex-direction: column
	min-height: 0
	min-width: 0
	height: 100vh
	width: 100%
	font-size: 14px
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
		width: 350px
		flex: none
</style>

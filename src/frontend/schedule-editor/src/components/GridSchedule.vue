<template lang="pug">
.c-grid-schedule()
	.grid(ref="grid", :style="gridStyle", :class="gridClasses", @pointermove="updateHoverSlice($event)", @pointerup="stopDragging()")
		template(v-for="slice of visibleTimeslices")
			.timeslice(:ref="slice.name", :class="getSliceClasses(slice)", :data-slice="slice.date.format()", :style="getSliceStyle(slice)", @click="expandTimeslice(slice)") {{ getSliceLabel(slice) }}
				svg(viewBox="0 0 10 10", v-if="isSliceExpandable(slice)").expand
					path(d="M 0 4 L 5 0 L 10 4 z")
					path(d="M 0 6 L 5 10 L 10 6 z")
			.timeseparator(:class="getSliceClasses(slice)", :style="getSliceStyle(slice)")
		.room(:style="{'grid-area': `1 / 1 / auto / auto`}")
		.room(v-for="(room, index) of rooms", :style="{'grid-area': `1 / ${index + 2 } / auto / auto`}") {{ getLocalizedString(room.name) }}
		session(v-if="draggedSession && hoverSlice", :style="getHoverSliceStyle()", :session="draggedSession", :isDragClone="true")
		template(v-for="session of sessions")
			session(
				:session="session",
				:isDragged="draggedSession && (session.id === draggedSession.id)",
				:style="getSessionStyle(session)",
				:showRoom="false",
				@startDragging="$emit('startDragging', $event)"
			)
</template>
<script>
// TODO
// - handle click on already selected day (needs some buntpapier hacking)
// - optionally only show venueless rooms
import moment from 'moment-timezone'
import Session from './Session'
import { getLocalizedString } from '~/utils'

const getSliceName = function (date) {
	return `slice-${date.format('MM-DD-HH-mm')}`
}

export default {
	components: { Session },
	props: {
		sessions: Array,
		rooms: Array,
		currentDay: Object,
		draggedSession: Object,
		scrollParent: Element
	},
	data () {
		return {
			moment,
			getLocalizedString,
			scrolledDay: null,
			hoverSlice: null,
			expandedTimeslices: [],
			gridOffset: 0,
		}
	},
	computed: {
		hoverSliceLegal () {
			if (!this.hoverSlice) return false
			const start = this.hoverSlice.time
			const end = this.hoverSlice.time.clone().add(this.draggedSession.duration, 'm')
			const sessionId = this.draggedSession.id
			const roomId = this.hoverSlice.room.id
			for (const session of this.sessions) {
				if (session.room.id === roomId && session.id !== sessionId) {
					// Test all same-room sessions for overlap with our new session:
					// Overlap exists if this session's start or end falls within our session
					if (session.start === start || session.end === end) return false
					if (session.start.isBetween(start, end) || session.end.isBetween(start, end)) return false
					// or the other way around (to take care of either session containing the other completely)
					if (start.isBetween(session.start, session.end) || end.isBetween(session.start, session.end)) return false
				}
			}
			return true
		},
		hoverEndSlice () {
			if (this.draggedSession && this.hoverSlice) {
				return this.hoverSlice.time.clone().add(this.hoverSlice.duration, 'm')
			}
			return null
		},
		timeslices () {
			const minimumSliceMins = 30
			const slices = []
			const slicesLookup = {}
			const pushSlice = function (date, {hasStart = false, hasEnd = false, hasSession = false} = {}) {
				const name = getSliceName(date)
				let slice = slicesLookup[name]
				if (slice) {
					slice.hasSession = slice.hasSession || hasSession
					slice.hasStart = slice.hasStart || hasStart
					slice.hasEnd = slice.hasEnd || hasEnd
				} else {
					slice = {
						date,
						name,
						hasSession,
						hasStart,
						hasEnd,
						datebreak: date.isSame(date.clone().startOf('day'))
					}
					slices.push(slice)
					slicesLookup[name] = slice
				}
			}
			const fillHalfHours = function (start, end, {hasSession} = {}) {
				// fill to the nearest half hour, then each half hour, then fill to end
				let mins = end.diff(start, 'minutes')
				const startingMins = minimumSliceMins - start.minute() % minimumSliceMins
				// buffer slices because we need to remove hasSession from the last one
				const halfHourSlices = []
				if (startingMins) {
					halfHourSlices.push(start.clone().add(startingMins, 'minutes'))
					mins -= startingMins
				}
				const endingMins = end.minute() % minimumSliceMins
				for (let i = 1; i <= mins / minimumSliceMins; i++) {
					halfHourSlices.push(start.clone().add(startingMins + minimumSliceMins * i, 'minutes'))
				}

				if (endingMins) {
					halfHourSlices.push(end.clone().subtract(endingMins, 'minutes'))
				}

				// last slice is actually just after the end of the session and has no session
				const lastSlice = halfHourSlices.pop()
				halfHourSlices.forEach(slice => pushSlice(slice, {hasSession}))
				pushSlice(lastSlice)
			}
			for (const session of this.sessions) {
				const lastSlice = slices[slices.length - 1]
				// gap to last slice
				if (!lastSlice) {
					pushSlice(session.start.clone().startOf('day'))
				} else if (session.start.isAfter(lastSlice.date, 'minutes')) {
					fillHalfHours(lastSlice.date, session.start)
				}

				// add start and end slices for the session itself
				pushSlice(session.start, {hasStart: true, hasSession: true})
				pushSlice(session.end, {hasEnd: true})
				// add half hour slices between a session
				fillHalfHours(session.start, session.end, {hasSession: true})
			}
			for (const slice of this.expandedTimeslices) {
				pushSlice(slice)
			}
			if (this.hoverEndSlice) pushSlice(this.hoverEndSlice)
			return [...new Set(slices)].sort((a, b) => a.date.diff(b.date))
		},
		visibleTimeslices () {
			// We show all half and full hour marks, plus all dates that were click-expanded, plus all start times of talks
			return this.timeslices.filter(slice => slice.date.minute() % 30 === 0 || this.expandedTimeslices.includes(slice.date) || this.oddTimeslices.includes(slice.date))
		},
		oddTimeslices () {
			const result = []
			this.sessions.forEach(session => {
				if (session.start.minute() % 30 !== 0) result.push(session.start)
			})
			return [...new Set(result)]
		},
		gridStyle () {
			let rows = '[header] 52px '
			rows += this.timeslices.map((slice, index) => {
				const next = this.timeslices[index + 1]
				let height = 60
				if (slice.gap) {
					height = 100
				} else if (slice.datebreak) {
					height = 60
				} else if (next) {
					height = Math.min(60, next.date.diff(slice.date, 'minutes') * 2)
				}
				return `[${slice.name}] minmax(${height}px, auto)`
			}).join(' ')
			return {
				'--total-rooms': this.rooms.length,
				'grid-template-rows': rows
			}
		},
		gridClasses () {
			const result = []
			if (this.draggedSession) result.push('is-dragging')
			if (this.hoverSlice && this.draggedSession && !this.hoverSliceLegal) result.push('illegal-hover')
			return result
		},
	},
	watch: {
		currentDay: 'changeDay'
	},
	async mounted () {
		await this.$nextTick()
		this.observer = new IntersectionObserver(this.onIntersect, {
			root: this.scrollParent,
			rootMargin: '-45% 0px'
		})
		for (const [ref, el] of Object.entries(this.$refs)) {
			if (!ref.startsWith('slice') || !ref.endsWith('00-00')) continue
			this.observer.observe(el[0])
		}
		this.gridOffset = this.$refs.grid.getBoundingClientRect().left
	},
	methods: {
		stopDragging () {
			if (!this.draggedSession || !this.hoverSlice || !this.hoverSliceLegal) return
			const start = this.hoverSlice.time
			const end = this.hoverSlice.time.clone().add(this.draggedSession.duration, 'm')
			this.$emit('rescheduleSession', {session: this.draggedSession, start: start.format(), end: end.format(), room: this.hoverSlice.room})
		},
		expandTimeslice (slice) {
			// Find next visible timeslice
			const index = this.visibleTimeslices.indexOf(slice)
			const time = slice.date.clone().add(5, 'm')
			if (index + 1 >= this.visibleTimeslices.length) {
				// last timeslice: add one more
				this.expandedTimeslices.push(time.clone())
			} else {
				const end = this.visibleTimeslices[index + 1].date.clone()
				while (time.isBefore(end)) {
					this.expandedTimeslices.push(time.clone())
					time.add(5, 'm')
				}
			}
			this.expandedTimeslices = [...new Set(this.expandedTimeslices)]
		},
		updateHoverSlice (e) {
			if (!this.draggedSession) { this.hoverSlice = null; return }
			let hoverSlice = null
			// We're grabbing the leftmost point of our y position and searching for the slice element there
		    // to determine our hover slice's attributes (y axis)
			for (const element of document.elementsFromPoint(this.gridOffset, e.clientY)) {
				if (element && element.dataset.slice && element.classList.contains('timeslice') && !element.classList.contains('datebreak')) {
					hoverSlice = element
					break
				}
			}
			if (!hoverSlice) return
			// For the x axis, we need to know which room we are in, so we divide our position by 
			const roomWidth = document.querySelectorAll('.grid .room')[1].getBoundingClientRect().width
			const roomIndex = Math.floor((e.clientX - this.gridOffset - 80) / roomWidth) // remove the timeline offset to the left
			console.log(roomIndex)
			this.hoverSlice = { time: moment(hoverSlice.dataset.slice), roomIndex: roomIndex, room: this.rooms[roomIndex], duration: this.draggedSession.duration }
		},
		getHoverSliceStyle () {
			if (!this.hoverSlice || !this.draggedSession) return
			return { 'grid-area': `${getSliceName(this.hoverSlice.time)} / ${this.hoverSlice.roomIndex + 2} / ${getSliceName(this.hoverSlice.time.clone().add(this.hoverSlice.duration, 'm'))}` }
		},
		getSessionStyle (session) {
			if (!session.room || !session.start) return {}
			const roomIndex = this.rooms.indexOf(session.room)
			return {
				'grid-row': `${getSliceName(session.start)} / ${getSliceName(session.end)}`,
				'grid-column': roomIndex > -1 ? roomIndex + 2 : null
			}
		},
		getOffsetTop () {
			const rect = this.$parent.$el.getBoundingClientRect()
			return rect.top + window.scrollY
		},
		getSliceClasses (slice) {
			const classes = {
				datebreak: slice.datebreak,
				gap: slice.gap,
				expandable: this.isSliceExpandable(slice)
			}
			return classes
		},
		isSliceExpandable (slice) {
			if (slice.gap) return false
			const index = this.visibleTimeslices.indexOf(slice)
			if (index + 1 === this.visibleTimeslices.length) return false
			const nextSlice = this.visibleTimeslices[index + 1]
			return nextSlice.date.diff(slice.date, 'm') > 5
		},
		getSliceStyle (slice) {
			if (slice.datebreak) {
				let index = this.timeslices.findIndex(s => s.date.isAfter(slice.date, 'day'))
				if (index < 0) {
					index = this.timeslices.length - 1
				}
				return {'grid-area': `${slice.name} / 1 / ${this.timeslices[index].name} / auto`}
			}
			return {'grid-area': `${slice.name} / 1 / auto / auto`}
		},
		getSliceLabel (slice) {
			if (slice.datebreak) return slice.date.format('ddd[\n]DD. MMM')
			return slice.date.format('LT')
		},
		changeDay (day) {
			if (this.scrolledDay === day) return
			const el = this.$refs[getSliceName(day)]?.[0]
			if (!el) return
			const offset = el.offsetTop + this.getOffsetTop()
			if (this.scrollParent) {
				this.scrollParent.scrollTop = offset
			} else {
				window.scroll({top: offset})
			}
		},
		onIntersect (entries) {
			// TODO still gets stuck when scrolling fast above threshold and back
			const entry = entries.sort((a, b) => b.time - a.time).find(entry => entry.isIntersecting)
			if (!entry) return
			const day = moment.parseZone(entry.target.dataset.slice).startOf('day')
			this.scrolledDay = day
			this.$emit('changeDay', this.scrolledDay)
		}
	}
}
</script>
<style lang="stylus">
.c-grid-schedule
	flex: auto
	.grid
		background-color: $clr-grey-50
		display: grid
		grid-template-columns: 78px repeat(var(--total-rooms), 1fr) auto
		// grid-gap: 8px
		position: relative
		min-width: min-content
		&.illegal-hover
			cursor: not-allowed !important
		> .room
			position: sticky
			top: calc(48px)
			display: flex
			justify-content: center
			align-items: center
			font-size: 18px
			background-color: $clr-white
			border-bottom: border-separator()
			z-index: 20
		.c-linear-schedule-session
			z-index: 10
	.timeslice
		color: $clr-secondary-text-light
		padding: 8px 10px 0 10px
		white-space: nowrap
		position: sticky
		left: 0
		text-align: center
		background-color: $clr-grey-50
		border-top: 1px solid $clr-dividers-light
		z-index: 20
		.expand
			display: none
		&.datebreak
			font-weight: 600
			border-top: 3px solid $clr-dividers-light
			white-space: pre
		&.expandable:hover
			background-color: $clr-grey-200
			cursor: pointer
			.expand
				display: block
				width: 20px
				margin: 4px auto
				path
					fill: $clr-grey-500

	.timeseparator
		height: 1px
		background-color: $clr-dividers-light
		position: absolute
		// transform: translate(-16px, -8px)
		width: 100%
		&.datebreak
			height: 3px
	.bunt-scrollbar-rail-wrapper-x, .bunt-scrollbar-rail-wrapper-y
		z-index: 30
</style>

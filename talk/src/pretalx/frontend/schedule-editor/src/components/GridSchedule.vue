<template lang="pug">
.c-grid-schedule()
	.grid(ref="grid", :style="gridStyle", :class="gridClasses", @pointermove="updateHoverSlice($event)", @pointerup="stopDragging($event)")
		template(v-for="slice of visibleTimeslices")
			.timeslice(:ref="slice.name", :class="getSliceClasses(slice)", :data-slice="slice.date.format()", :style="getSliceStyle(slice)", @click="expandTimeslice(slice)") {{ getSliceLabel(slice) }}
				svg(viewBox="0 0 10 10", v-if="isSliceExpandable(slice)").expand
					path(d="M 0 4 L 5 0 L 10 4 z")
					path(d="M 0 6 L 5 10 L 10 6 z")
			.timeseparator(:class="getSliceClasses(slice)", :style="getSliceStyle(slice)")
		.room(:style="{'grid-area': `1 / 1 / auto / auto`}")
		.room(v-for="(room, index) of visibleRooms", :style="{'grid-area': `1 / ${index + 2 } / auto / auto`}")
			span {{ getLocalizedString(room.name) }}
			.hide-room.no-print(v-if="visibleRooms.length > 1", @click="hiddenRooms = rooms.filter(r => hiddenRooms.includes(r) || r === room)")
				i.fa.fa-eye-slash
		session(v-if="draggedSession && hoverSlice", :style="getHoverSliceStyle()", :session="draggedSession", :isDragClone="true", :overrideStart="hoverSlice.time")
		template(v-for="session of visibleSessions")
			session(
				:session="session",
				:warnings="session.code ? warnings[session.code] : []",
				:isDragged="draggedSession && (session.id === draggedSession.id)",
				:style="getSessionStyle(session)",
				:showRoom="false",
				@startDragging="startDragging($event)",
			)
		.availability(v-for="availability of visibleAvailabilities", :style="getSessionStyle(availability)", :class="availability.active ? ['active'] : []")
	#hiddenRooms.no-print(v-if="hiddenRooms.length")
		h4 {{ $t('Hidden rooms') }} ({{ hiddenRooms.length }})
		.room-list
			.room-entry(v-for="room of hiddenRooms", @click="hiddenRooms.splice(hiddenRooms.indexOf(room), 1)")
				.span {{ getLocalizedString(room.name) }}
				.show-room(@click.stop="hiddenRooms.splice(hiddenRooms.indexOf(room), 1)")
					i.fa.fa-eye

</template>
<script>
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
		availabilities: Object,
		warnings: Object,
		start: Object,
		end: Object,
		rooms: Array,
		currentDay: Object,
		draggedSession: Object
	},
	data () {
		return {
			moment,
			getLocalizedString,
			scrolledDay: null,
			hoverSlice: null,
			expandedTimes: [],
			gridOffset: 0,
			dragScrollTimer: null,
			dragStart: null,
			hiddenRooms: [],
		}
	},
	computed: {
		hoverSliceLegal () {
			if (!this.hoverSlice || !this.hoverSlice.room) return false
			const start = this.hoverSlice.time
			const end = this.hoverSlice.time.clone().add(this.draggedSession.duration, 'm')
			const sessionId = this.draggedSession.id
			const roomId = this.hoverSlice.room.id
			for (const session of this.sessions.filter(s => s.start)) {
				if (session.room.id === roomId && session.id !== sessionId) {
					// Test all same-room sessions for overlap with our new session:
					// Overlap exists if this session's start or end falls within our session
					if (session.start.isSame(start) || session.end.isSame(end)) return false
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
			const pushSlice = function (date, {hasStart = false, hasEnd = false, hasSession = false, isExpanded = false} = {}) {
				const name = getSliceName(date)
				let slice = slicesLookup[name]
				if (slice) {
					slice.hasSession = slice.hasSession || hasSession
					slice.hasStart = slice.hasStart || hasStart
					slice.hasEnd = slice.hasEnd || hasEnd
					slice.isExpanded = slice.isExpanded || isExpanded
				} else {
					slice = {
						date,
						name,
						hasSession,
						hasStart,
						hasEnd,
						isExpanded,
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
			for (const slice of this.expandedTimes) {
				pushSlice(slice, {isExpanded: true})
			}
			// Always show business hours
			fillHalfHours(this.start, this.end)
			if (this.hoverEndSlice) pushSlice(this.hoverEndSlice, {hasEnd: true})
			const sliceIsFraction = function (slice) {
				if (!slice) return
				return slice.date.minutes() !== 0 && slice.date.minutes() !== minimumSliceMins
			}
			const sliceShouldDisplay = function (slice, index) {
				if (!slice) return
				// keep slices with sessions or when changing dates, or when sessions start or immediately after they end
				if (slice.hasSession || slice.datebreak || slice.hasStart || slice.hasEnd || slice.isExpanded) return true
				// keep slices between 9 and 18 o'clock
				if (slice.date.hour() >= 9 && slice.date.hour() < 19) return true
				const prevSlice = slices[index - 1]
				const nextSlice = slices[index + 1]

				// keep non-whole slices
				if (sliceIsFraction(slice)) return true
				// keep slices before and after non-whole slices, if by session or break
				if (
					((prevSlice?.hasSession || prevSlice?.hasBreak || prevSlice?.hasEnd) && sliceIsFraction(prevSlice)) ||
					((nextSlice?.hasSession || nextSlice?.hasBreak) && sliceIsFraction(nextSlice)) ||
					((!nextSlice?.hasSession || !nextSlice?.hasBreak) && (slice.hasSession || slice.hasBreak) && sliceIsFraction(nextSlice))
				) return true
				// but drop slices inside breaks
				if (prevSlice?.hasBreak && slice.hasBreak) return false
				return false
			}
			slices.sort((a, b) => a.date.diff(b.date))
			const compactedSlices = []
			for (const [index, slice] of slices.entries()) {
				if (sliceShouldDisplay(slice, index)) {
					compactedSlices.push(slice)
					continue
				}
				// make the previous slice a gap slice if this one would be the first to be removed
				// but only if it isn't the start of the day
				const prevSlice = slices[index - 1]
				if (sliceShouldDisplay(prevSlice, index - 1) && !prevSlice.datebreak) {
					prevSlice.gap = true
				}
			}
			return compactedSlices
		},
		visibleTimeslices () {
			// Inside normal conference hours, from 9am to 6pm, we show all half and full hour marks, plus all dates that were click-expanded, plus all start times of talks
			// Outside, we only show the first slice, which can be expanded
		  return this.timeslices.filter(slice => {
			  return slice.date.minute() % 30 === 0 || this.expandedTimes.includes(slice.date) || this.oddTimeslices.includes(slice.date)
		  })
		},
		oddTimeslices () {
			const result = []
			this.sessions.forEach(session => {
				if (session.start.minute() % 30 !== 0) result.push(session.start)
				if (session.end.minute() % 30 !== 0) result.push(session.end)
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
				'--total-rooms': this.visibleRooms.length,
				'grid-template-rows': rows
			}
		},
		gridClasses () {
			const result = []
			if (this.draggedSession) result.push('is-dragging')
			if (this.hoverSlice && this.draggedSession && !this.hoverSliceLegal) result.push('illegal-hover')
			return result
		},
		availabilitySlices () {
			const avails = []
			if (!this.visibleTimeslices?.length) return avails
			const earliestStart = this.visibleTimeslices[0].date
			const latestEnd = this.visibleTimeslices.at(-1).date
			const draggedAvails = []
			if (this.draggedSession && this.availabilities.talks[this.draggedSession.id]?.length) {
				for (const avail of this.availabilities.talks[this.draggedSession.id]) {
					draggedAvails.push({
						start: moment(avail.start),
						end: moment(avail.end),
					})
				}
			}
			for (const room of this.visibleRooms) {
				if (!this.availabilities.rooms[room.id] || !this.availabilities.rooms[room.id].length) avails.push({room: room, start: earliestStart, end: latestEnd})
				else {
					for (const avail of this.availabilities.rooms[room.id]) {
						avails.push({
							room: room,
							start: moment(avail.start),
							end: moment(avail.end)
						})
					}
				}
				for (const avail of draggedAvails) {
					avails.push({
						room: room,
						start: avail.start,
						end: avail.end,
						active: true
					})
				}
			}
			return avails
		},
		staticOffsetTop () {
			const rect = this.$parent.$el.getBoundingClientRect()
			return rect.top
		},
		scrollParent () {
			return this.$refs.grid.parentElement.parentElement
		},
		visibleRooms () {
			return this.rooms.filter(room => !this.hiddenRooms.includes(room))
		},
		visibleSessions () {
			// only show sessions whose rooms are not in this.hiddenRooms
			return this.sessions.filter(session => !this.hiddenRooms.includes(session.room))
		},
		visibleAvailabilities () {
			// Filter out availabilities for hidden rooms
			// and shorten all availabilities to the visible timeslices
			const result = []
			for (const avail of this.availabilitySlices) {
				if (this.hiddenRooms.includes(avail.room)) continue
				const start = this.visibleTimeslices.find(slice => slice.date.isSameOrAfter(avail.start))
				const end = this.visibleTimeslices.find(slice => slice.date.isSameOrAfter(avail.end))
				if (!start || !end) continue
				result.push({
					room: avail.room,
					start: start.date,
					end: end.date,
					active: avail.active
				})
			}
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
		startDragging({session, event}) {
			this.dragStart = {
				x: event.clientX,
				y: event.clientY,
				session: session,
				now: moment(),
			}
			this.$emit('startDragging', {event, session})
		},
		stopDragging (event) {
			if (this.dragStart && this.draggedSession) {
				const distance = this.dragStart.x - event.clientX + this.dragStart.y - event.clientY
				const timeDiff = moment().diff(this.dragStart.now, 'ms')
				const session = this.dragStart.session
				this.dragStart = null
				// if this looks like a click, emit a click event
				if (distance < 5 && distance > -5 && timeDiff < 500) {
					this.$emit('editSession', session)
					return
				}
			}
			if (!this.draggedSession || !this.hoverSlice || !this.hoverSliceLegal) return
			const start = this.hoverSlice.time
			const end = this.hoverSlice.time.clone().add(this.draggedSession.duration, 'm')
			if (!this.draggedSession.id) {
			  this.$emit('createSession', {session: {...this.draggedSession, start: start.format(), end: end.format(), room: this.hoverSlice.room.id}})
			} else {
				this.$emit('rescheduleSession', {session: this.draggedSession, start: start.format(), end: end.format(), room: this.hoverSlice.room})
			}
		},
		expandTimeslice (slice) {
			// Find next visible timeslice
			const index = this.visibleTimeslices.indexOf(slice)
			if (index + 1 >= this.visibleTimeslices.length) {
				// last timeslice: add five more minutes
				this.expandedTimes.push(slice.date.clone().add(5, 'm'))
			} else {
				const end = this.visibleTimeslices[index + 1].date.clone()
				// if next time slice is within 30 minutes, set interval to 5 minutes, otherwise to 30 minutes
				let interval = 0
				if (end.diff(slice.date, 'minutes') <= 30) {
					interval = 5
				} else {
					interval = 30
				}
				const time = slice.date.clone().add(interval, 'm')
				while (time.isBefore(end)) {
					this.expandedTimes.push(time.clone())
					time.add(interval, 'm')
				}
			}
			this.expandedTimes = [...new Set(this.expandedTimes)]
		},
		updateHoverSlice (e) {
			if (!this.draggedSession) { this.hoverSlice = null; return }
			if (!this.dragScrollTimer) {
				this.dragScrollTimer = setInterval(this.dragOnScroll, 100)
			}
			let hoverSlice = null
			this.draggedSession.event = e
			// We're grabbing the leftmost point of our y position and searching for the slice element there
		    // to determine our hover slice's attributes (y axis)
			for (const element of document.elementsFromPoint(this.gridOffset, e.clientY)) {
				if (element && element.dataset.slice && element.classList.contains('timeslice')) {
					hoverSlice = element
					break
				}
			}
			if (!hoverSlice) return
			// For the x axis, we need to know which room we are in, so we divide our position by
			const roomWidth = document.querySelectorAll('.grid .room')[1].getBoundingClientRect().width
			// We need to know if our container is scrolled to the right
			const scrollOffset = this.scrollParent.scrollLeft
			const roomIndex = Math.floor((e.clientX + scrollOffset - this.gridOffset - 80) / roomWidth) // remove the timeline offset to the left
			this.hoverSlice = { time: moment(hoverSlice.dataset.slice), roomIndex: roomIndex, room: this.visibleRooms[roomIndex], duration: this.draggedSession.duration }
		},
		getHoverSliceStyle () {
			if (!this.hoverSlice || !this.draggedSession) return
			return { 'grid-area': `${getSliceName(this.hoverSlice.time)} / ${this.hoverSlice.roomIndex + 2} / ${getSliceName(this.hoverSlice.time.clone().add(this.hoverSlice.duration, 'm'))}` }
		},
		getSessionStyle (session) {
			if (!session.room || !session.start) return {}
			const roomIndex = this.visibleRooms.indexOf(session.room)
			return {
				'grid-row': `${getSliceName(session.start)} / ${getSliceName(session.end)}`,
				'grid-column': roomIndex > -1 ? roomIndex + 2 : null
			}
		},
		getOffsetTop () {
			return this.staticOffsetTop + window.scrollY
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
			this.scrollTo(offset)
		},
		scrollTo (offset) {
			this.scrollParent.scroll({top: offset, behavior: "smooth"})
		},
		scrollBy (offset) {
			this.scrollParent.scrollBy({top: offset, behavior: "smooth"})
		},
		dragOnScroll () {
			if (!this.draggedSession) {
				clearInterval(this.dragScrollTimer)
				this.dragScrollTimer = null;
				return
			}
			// get current mouse y position
			const event = this.draggedSession.event
			if (event.clientY - this.staticOffsetTop < 160) {
				if (event.clientY - this.staticOffsetTop < 90) {
					this.scrollBy(-200)
				} else {
					this.scrollBy(-75)
				}
			} else if (event.clientY > this.scrollParent.clientHeight + this.staticOffsetTop - 100) {
				if (event.clientY > this.scrollParent.clientHeight + this.staticOffsetTop - 40) {
					this.scrollBy(200)
				} else {
					this.scrollBy(75)
				}
			}
		},
		onIntersect (entries) {
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
			.c-linear-schedule-session
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
			.hide-room
				color: $clr-secondary-text-light
				font-size: 14px
				margin-left: 16px
				cursor: pointer
				padding: 4px 8px
				border-radius: 4px
				&:hover
					background-color: $clr-grey-200
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
.availability
	background-color: white
	pointer-events: none
	&.active
		background-color: rgba(56, 158, 119, 0.1)
#hiddenRooms
	position: fixed
	z-index: 500
	bottom: 0
	right: 0
	width: 300px;
	background-color: $clr-white
	padding: 8px 16px
	box-shadow: 0 0 10px rgba(0, 0, 0, 0.3)
	border-top-left-radius: 8px
	font-size: 16px

	.room-list
		display: none

	&:hover
		.room-list
			display: block

	.room-entry
		border-bottom: border-separator()
		display: flex
		justify-content: space-between
		align-items: center
		height: 28px
		padding: 4px 0
		cursor: pointer
		.show-room
			color: $clr-secondary-text-light
			font-size: 14px
			margin-left: 16px
			padding: 4px 8px
			border-radius: 4px
		&:hover
			background-color: $clr-grey-100
</style>

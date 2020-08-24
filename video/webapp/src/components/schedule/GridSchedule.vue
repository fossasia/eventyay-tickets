<template lang="pug">
.c-grid-schedule(v-scrollbar.x.y="")
	.grid(:style="gridStyle")
		template(v-for="slice of visibleTimeslices")
			.timeslice(:ref="slice.name", :class="{datebreak: slice.datebreak}", :data-slice="slice.date.toISOString()", :style="getSliceStyle(slice)") {{ slice.datebreak ? slice.date.format('dddd DD. MMMM') : slice.date.format('LT') }}
			.timeline(:class="{datebreak: slice.datebreak}", :style="getSliceStyle(slice)")
		//- .nowline(v-if="nowSlice", :style="{'grid-area': `${nowSlice.slice.name} / 1 / auto / auto`, '--offset': nowSlice.offset}")
		.now(v-if="nowSlice", ref="now", :style="{'grid-area': `${nowSlice.slice.name} / 1 / auto / auto`, '--offset': nowSlice.offset}")
			svg(viewBox="0 0 10 10")
				path(d="M 0 0 L 10 5 L 0 10 z")
		.room(:style="{'grid-area': `1 / 1 / auto / auto`}")
		.room(v-for="(room, index) of rooms", :style="{'grid-area': `1 / ${index + 2 } / auto / auto`}") {{ getLocalizedString(room.name) }}
		.room(v-if="hasSessionsWithoutRoom", :style="{'grid-area': `1 / ${rooms.length + 2} / auto / -1`}") sonstiger Ramsch
		template(v-for="session of sessions")
			session(v-if="session.id", :session="session", :style="getSessionStyle(session)")
			.break(v-else, :style="getSessionStyle(session)")
				.title {{ getLocalizedString(session.title) }}
</template>
<script>
// TODO
// - handle click on already selected day (needs some buntpapier hacking)
// - sessions spanning days collide with datebreaks
import { mapState, mapGetters } from 'vuex'
import moment from 'lib/timetravelMoment'
import Session from './Session'
import { getLocalizedString } from './utils'

const getSliceName = function (date) {
	return `slice-${date.format('MM-DD-HH-mm')}`
}

export default {
	components: { Session },
	props: {
		currentDay: Object
	},
	data () {
		return {
			moment,
			getLocalizedString,
			scrolledDay: null
		}
	},
	computed: {
		...mapState('schedule', ['schedule', 'now']),
		...mapGetters('schedule', ['sessions']),
		hasSessionsWithoutRoom () {
			return this.sessions.some(s => !s.room)
		},
		rooms () {
			// TODO optionally only show venueless rooms
			return this.schedule.rooms
		},
		timeslices () {
			const minimumSliceMins = 30
			const slices = []
			const slicesLookup = {}
			const pushSlice = function (date, datebreak) {
				const name = getSliceName(date)
				if (slicesLookup[name]) return
				slices.push({
					date,
					name,
					datebreak
				})
				slicesLookup[name] = true
			}
			const fillHalfHours = function (start, end) {
				// fill to the nearest half hour, then each half hour, then fill to end
				let mins = end.diff(start, 'minutes')
				const startingMins = start.minute() % minimumSliceMins
				if (startingMins) {
					pushSlice(start.clone().add(startingMins, 'minutes'))
					mins -= startingMins
				}
				for (let i = 1; i <= mins / minimumSliceMins; i++) {
					pushSlice(start.clone().add(startingMins + minimumSliceMins * i, 'minutes'))
				}
				const endingMins = end.minute() % minimumSliceMins
				if (endingMins) {
					pushSlice(end.clone().subtract(endingMins, 'minutes'))
				}
			}
			for (const session of this.sessions) {
				const lastSlice = slices[slices.length - 1]
				// gap to last slice
				if (!lastSlice) {
					pushSlice(session.start.clone().startOf('day'), true)
				} else if (session.start.isAfter(lastSlice.date, 'minutes')) {
					if (session.start.isSame(lastSlice.date, 'day')) {
						// pad slices in gaps for same day
						fillHalfHours(lastSlice.date, session.start)
					} else {
						// add date break
						// TODO avoid overlaps
						pushSlice(lastSlice.date.clone().add(minimumSliceMins, 'minutes'))
						pushSlice(session.start.clone().startOf('day'), true)
					}
				}

				// add start and end slices for the session itself
				pushSlice(session.start)
				pushSlice(session.end)
				// add half hour slices between a session
				fillHalfHours(session.start, session.end)
			}
			slices.sort((a, b) => a.date.diff(b.date))
			return slices
		},
		visibleTimeslices () {
			return this.timeslices.filter(slice => slice.date.minute() % 30 === 0)
		},
		gridStyle () {
			let rows = '[header] 52px '
			rows += this.timeslices.map((slice, index) => {
				const next = this.timeslices[index + 1]
				let height = 60
				if (next) {
					height = Math.min(30, next.date.diff(slice.date, 'minutes'))
				}
				if (slice.datebreak) {
					return `[${slice.name}] minmax(48px, auto)`
				} else {
					return `[${slice.name}] minmax(${height}px, auto)`
				}
			}).join(' ')
			return {
				'--total-rooms': this.schedule.rooms.length,
				'grid-template-rows': rows
			}
		},
		nowSlice () {
			let slice
			for (const s of this.timeslices) {
				if (this.now.isBefore(s.date)) break
				slice = s
			}
			if (slice) {
				const nextSlice = this.timeslices[this.timeslices.indexOf(slice) + 1]
				if (!nextSlice) return null
				return {
					slice,
					offset: this.now.diff(slice.date, 'minutes') / nextSlice.date.diff(slice.date, 'minutes')
				}
			}
			return null
		}
	},
	watch: {
		currentDay: 'changeDay'
	},
	async mounted () {
		await this.$nextTick()
		this.observer = new IntersectionObserver(this.onIntersect, {
			root: this.$el,
			rootMargin: '-45% 0px'
		})
		for (const [ref, el] of Object.entries(this.$refs)) {
			if (!ref.startsWith('slice') || !ref.endsWith('00-00')) continue
			this.observer.observe(el[0])
		}
		// scroll to now
		if (!this.$refs.now) return
		this.$el.scrollTop = this.$refs.now.offsetTop - 90
	},
	methods: {
		getSessionStyle (session) {
			const roomIndex = this.rooms.indexOf(session.room)
			return {
				'grid-row': `${getSliceName(session.start)} / ${getSliceName(session.end)}`,
				'grid-column': roomIndex > -1 ? roomIndex + 2 : null
			}
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
		changeDay (day) {
			if (this.scrolledDay === day) return
			const el = this.$refs[getSliceName(day)]?.[0]
			if (!el) return
			const offset = el.offsetTop - 52
			this.$el.scrollTop = offset
		},
		onIntersect (entries) {
			// TODO still gets stuck when scrolling fast above threshold and back
			const entry = entries.sort((a, b) => b.time - a.time).find(entry => entry.isIntersecting)
			if (!entry) return
			const day = moment(entry.target.dataset.slice).startOf('day')
			this.scrolledDay = day
			this.$emit('changeDay', this.scrolledDay)
		}
	}
}
</script>
<style lang="stylus">
.c-grid-schedule
	flex: auto
	background-color: $clr-grey-50
	.grid
		display: grid
		grid-template-columns: 80px repeat(var(--total-rooms), 1fr) auto
		// grid-gap: 8px
		position: relative
		min-width: min-content
		> .room
			position: sticky
			top: 0
			display: flex
			justify-content: center
			align-items: center
			font-size: 18px
			background-color: $clr-white
			border-bottom: border-separator()
			z-index: 20
		.c-linear-schedule-session
			z-index: 10
		.break
			z-index: 10
			margin: 8px
			// border: border-separator()
			border-radius: 4px
			background-color: $clr-grey-200
			display: flex
			justify-content: center
			align-items: center
			.title
				font-size: 20px
				font-weight: 500
				color: $clr-secondary-text-light
	.timeslice
		color: $clr-secondary-text-light
		padding: 8px 0 0 16px
		white-space: nowrap
		min-height: 48px
		position: sticky
		left: 0
		background-color: $clr-grey-50
		border-top: 1px solid $clr-dividers-light
		z-index: 20
		&.datebreak
			font-weight: 600
			border-top: 3px solid $clr-dividers-light
	.timeline
		height: 1px
		background-color: $clr-dividers-light
		position: absolute
		// transform: translate(-16px, -8px)
		width: 100%
		&.datebreak
			height: 3px
	.nowline
		height: 2px
		background-color: $clr-red
		position: absolute
		transform: translate(0, calc(var(--offset) * 100%))
		width: 100%
	.now
		margin-left: 2px
		z-index: 20
		position: relative
		&::before
			content: ''
			display: block
			height: 2px
			background-color: $clr-red
			position: absolute
			top: calc(var(--offset) * 100%)
			width: 100%
		svg
			position: absolute
			top: calc(var(--offset) * 100% - 11px)
			height: 24px
			width: 24px
			fill: $clr-red
	.bunt-scrollbar-rail-wrapper-x, .bunt-scrollbar-rail-wrapper-y
		z-index: 30
</style>

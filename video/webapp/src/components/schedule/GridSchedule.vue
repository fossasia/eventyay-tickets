<template lang="pug">
.c-grid-schedule(v-scrollbar.x.y="")
	.grid(:style="gridStyle")
		template(v-for="slice of visibleTimeslices")
			.timeslice(:ref="slice.name", :class="{datebreak: slice.datebreak}", :data-slice="slice.date.toISOString()", :style="getSliceStyle(slice)") {{ slice.datebreak ? slice.date.format('dddd DD. MMMM') : slice.date.format('LT') }}
			.timeline(:class="{datebreak: slice.datebreak}", :style="getSliceStyle(slice)")
		.now(v-if="nowSlice", ref="now", :style="{'grid-area': `${nowSlice.slice.name} / 1 / auto / auto`, '--offset': nowSlice.offset}")
			svg(viewBox="0 0 10 10")
				path(d="M 0 0 L 10 5 L 0 10 z")
		.room(:style="{'grid-area': `1 / 1 / auto / auto`}")
		.room(v-for="(room, index) of rooms", :style="{'grid-area': `1 / ${index + 2 } / auto / auto`}") {{ getLocalizedString(room.name) }}
		.room(v-if="hasSessionsWithoutRoom", :style="{'grid-area': `1 / ${rooms.length + 2} / auto / -1`}") sonstiger Ramsch
		session(v-for="session of sessions", :session="session", :style="getSessionStyle(session)")
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
	return `slice-${date.format('YYYY-MM-DD-HH-mm')}`
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
		// find this to not tax the grid with 1min rows
		greatestCommonDurationDivisor () {
			const gcd = (a, b) => a ? gcd(b % a, a) : b
			// don't allow some silly divisor like 1 to ruin the layout
			// TODO correctly place talks starting at odd times
			return Math.max(this.sessions
				.map(s => s.end.diff(s.start, 'minutes'))
				.reduce(gcd), 5)
		},
		timeslices () {
			const gcdd = this.greatestCommonDurationDivisor
			const slices = []
			for (const session of this.sessions) {
				const pushSlice = function (date, datebreak) {
					slices.push({
						date,
						name: getSliceName(date),
						datebreak
					})
				}
				let lastSlice = slices[slices.length - 1]
				// gap to last slice
				if (!lastSlice) {
					pushSlice(session.start.clone().startOf('day'), true)
				} else if (session.start.isAfter(lastSlice.date, 'minutes')) {
					if (session.start.isSame(lastSlice.date, 'day')) {
						// pad slices in gaps for same day
						const mins = session.start.diff(lastSlice.date, 'minutes')
						for (let i = 1; i <= mins / gcdd; i++) {
							pushSlice(lastSlice.date.clone().add(gcdd * i, 'minutes'))
						}
					} else {
						// add date break
						pushSlice(lastSlice.date.clone().add(gcdd, 'minutes'))
						pushSlice(session.start.clone().startOf('day'), true)
					}
				}

				const mins = session.end.diff(session.start, 'minutes')
				for (let i = 0; i < mins / gcdd; i++) {
					const date = session.start.clone().add(gcdd * i, 'minutes')
					lastSlice = slices[slices.length - 1]
					if (lastSlice && !date.isAfter(lastSlice.date, 'minutes')) continue
					pushSlice(date)
				}
			}
			console.log(slices.length)
			return slices
		},
		visibleTimeslices () {
			return this.timeslices.filter(slice => slice.date.minute() % 30 === 0)
		},
		gridStyle () {
			let rows = '[header] 52px '
			const rowHeight = this.greatestCommonDurationDivisor * 2 // or '1fr' for equal sizes
			rows += this.timeslices.map(slice => {
				if (slice.datebreak) {
					return `[${slice.name}] minmax(48px, auto)`
				} else {
					return `[${slice.name}] minmax(${rowHeight}px, auto)`
				}
			}).join(' ')
			return {
				'--row-height': this.greatestCommonDurationDivisor,
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
				return {
					slice,
					offset: this.now.diff(slice.date, 'minutes')
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
			const durationMinutes = session.end.diff(session.start, 'minutes')
			const height = Math.ceil(durationMinutes / this.greatestCommonDurationDivisor)
			const roomIndex = this.rooms.indexOf(session.room)
			return {
				'grid-row': `${getSliceName(session.start)} / span ${height}`,
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
	.now
		margin-left: 2px
		&::before
			content: ''
			display: block
			height: 2px
			background-color: $clr-red
			position: absolute
			transform: translate(0, calc(var(--offset) * 2px))
			width: calc(100% - 4px)
		svg
			transform: translateY(calc(var(--offset) * 2px - 11px))
			height: 24px
			width: 24px
			fill: $clr-red
	.bunt-scrollbar-rail-wrapper-x, .bunt-scrollbar-rail-wrapper-y
		z-index: 30
</style>

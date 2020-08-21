<template lang="pug">
.c-grid-schedule
	bunt-tabs.days(v-if="pretalxEvent.schedule.length > 1", :active-tab="currentDay.toISOString()")
		bunt-tab(v-for="day in days", :id="day.toISOString()", :header="moment(day).format('dddd DD. MMMM')", @selected="changeDay(day)")
	scrollbars(ref="scrollbars", y, x)
		.grid(:style="gridStyle")
			.timeslice(v-for="slice of timeslices", :ref="slice.name", :class="{datebreak: slice.datebreak}", :data-slice="slice.date.toISOString()", :style="{'grid-area': `${slice.name} / 1 / auto / auto`}") {{ slice.datebreak ? slice.date.format('dddd DD. MMMM') : slice.date.format('LT') }}
			.now(v-if="nowSlice", ref="now", :style="{'grid-area': `${nowSlice.slice.name} / 1 / auto / auto`, '--offset': nowSlice.offset}")
				svg(viewBox="0 0 10 10")
					path(d="M 0 0 L 10 5 L 0 10 z")
			.room(:style="{'grid-area': `1 / 1 / auto / auto`}")
			.room(v-for="(room, index) of rooms", :style="{'grid-area': `1 / ${index + 2 } / auto / auto`}") {{ room.name }}
			session(v-for="session of sessions", :session="session", :style="getSessionStyle(session)")
</template>
<script>
// TODO
// handle click on already selected day (needs some buntpapier hacking)
import { mapState, mapGetters } from 'vuex'
import moment from 'lib/timetravelMoment'
import Session from './Session'

const getSliceName = function (date) {
	return `slice-${date.format('YYYY-MM-DD-HH-mm')}`
}

export default {
	components: { Session },
	data () {
		return {
			moment,
			currentDay: moment().startOf('day')
		}
	},
	computed: {
		...mapState(['schedule', 'pretalxEvent', 'pretalxRooms', 'now']),
		...mapGetters(['flatSchedule']),
		sessions () {
			return this.flatSchedule?.sessions
		},
		rooms () {
			return this.pretalxRooms.map(room => this.$store.state.rooms.find(r => r.pretalx_id === room.id))
		},
		days () {
			return this.pretalxEvent.schedule.map(day => moment(day.start).startOf('day'))
		},
		// find this to not tax the grid with 1min rows
		greatestCommonDurationDivisor () {
			const gcd = (a, b) => a ? gcd(b % a, a) : b
			return this.sessions
				.map(s => s.end.diff(s.start, 'minutes'))
				.reduce(gcd)
		},
		totalRows () {
			const days = this.pretalxEvent.schedule
			const totalMinutes = moment(days[days.length - 1].end).diff(days[0].start, 'minutes')
			return Math.ceil(totalMinutes / this.greatestCommonDurationDivisor)
		},
		timeslices () {
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
					if (session.start.clone().startOf('day').isSame(lastSlice.date.clone().startOf('day'))) {
						// pad slices in gaps for same day
						const mins = session.start.diff(lastSlice.date, 'minutes')
						for (let i = 1; i <= mins / this.greatestCommonDurationDivisor; i++) {
							pushSlice(lastSlice.date.clone().add(this.greatestCommonDurationDivisor * i, 'minutes'))
						}
					} else {
						// add date break
						pushSlice(lastSlice.date.clone().add(this.greatestCommonDurationDivisor, 'minutes'))
						pushSlice(session.start.clone().startOf('day'), true)
					}
				}

				const mins = session.end.diff(session.start, 'minutes')
				for (let i = 0; i < mins / this.greatestCommonDurationDivisor; i++) {
					const date = session.start.clone().add(this.greatestCommonDurationDivisor * i, 'minutes')
					lastSlice = slices[slices.length - 1]
					if (lastSlice && !date.isAfter(lastSlice.date, 'minutes')) continue
					pushSlice(date)
				}
			}
			return slices
		},
		gridStyle () {
			let rows = '[header] 52px '
			const rowHeight = this.greatestCommonDurationDivisor * 2 // or '1fr' for equal sizes
			rows += this.timeslices.map(slice => `[${slice.name}] minmax(${rowHeight}px, auto)`).join(' ')
			return {
				'--row-height': this.greatestCommonDurationDivisor,
				'--total-rows': this.totalRows,
				'--total-rooms': this.pretalxRooms.length,
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
	async mounted () {
		await this.$nextTick()
		this.observer = new IntersectionObserver(this.onIntersect, {
			root: this.$refs.scrollbars.$refs.content,
			rootMargin: '-45% 0px'
		})
		for (const [ref, el] of Object.entries(this.$refs)) {
			if (!ref.startsWith('slice') || !ref.endsWith('00-00')) continue
			this.observer.observe(el[0])
		}
		// scroll to now
		if (!this.$refs.now) return
		this.$refs.scrollbars.scrollTop(this.$refs.now.offsetTop - 90)
	},
	methods: {
		getSessionStyle (session) {
			const durationMinutes = session.end.diff(session.start, 'minutes')
			const height = Math.ceil(durationMinutes / this.greatestCommonDurationDivisor)
			const roomIndex = this.pretalxRooms.findIndex(r => r.id === session.room.pretalx_id)
			return {
				'grid-row': `${getSliceName(session.start)} / span ${height}`,
				'grid-column': `${roomIndex + 2}`
			}
		},
		changeDay (day) {
			if (day.isSame(this.currentDay)) return
			this.currentDay = day
			const el = this.$refs[getSliceName(day)]?.[0]
			if (!el) return
			const offset = el.offsetTop - 52
			this.$refs.scrollbars.scrollTop(offset)
		},
		onIntersect (results) {
			const intersection = results[0]
			const day = moment(intersection.target.dataset.slice).startOf('day')
			if (intersection.isIntersecting) {
				this.currentDay = day
			} else if ((intersection.boundingClientRect.y - intersection.rootBounds.y) > 0) {
				this.currentDay = day.subtract(1, 'day')
			}
		}
	}
}
</script>
<style lang="stylus">
.c-grid-schedule
	flex: auto
	display: flex
	flex-direction: column
	.days
		background-color: $clr-white
		tabs-style(active-color: var(--clr-primary), indicator-color: var(--clr-primary), background-color: transparent)
		margin-bottom: 0
		.bunt-tabs-header-items
			justify-content: center
	.grid
		display: grid
		grid-template-columns: 240px repeat(var(--total-rooms), 1fr)
		// grid-gap: 8px
		position: relative
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
			margin: 8px
	.timeslice
		color: $clr-secondary-text-light
		padding: 8px 0 0 16px
		&::before
			content: ''
			display: block
			height: 1px
			background-color: $clr-dividers-light
			position: absolute
			transform: translate(-16px, -8px)
			width: 100%
		&.datebreak
			font-weight: 600
			&::before
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
			width: 100%
		svg
			transform: translateY(calc(var(--offset) * 2px - 11px))
			height: 24px
			width: 24px
			fill: $clr-red

</style>

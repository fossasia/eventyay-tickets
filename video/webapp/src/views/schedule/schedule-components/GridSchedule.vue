<template lang="pug">
.c-grid-schedule()
	.grid(:style="gridStyle")
		template(v-for="slice of visibleTimeslices")
			.timeslice(:ref="slice.name", :class="getSliceClasses(slice)", :data-slice="slice.date.format()", :style="getSliceStyle(slice)") {{ getSliceLabel(slice) }}
			.timeline(:class="getSliceClasses(slice)", :style="getSliceStyle(slice)")
		.now(v-if="nowSlice", ref="now", :class="{'on-daybreak': nowSlice.onDaybreak}", :style="{'grid-area': `${nowSlice.slice.name} / 1 / auto / auto`, '--offset': nowSlice.offset}")
			svg(viewBox="0 0 10 10")
				path(d="M 0 0 L 10 5 L 0 10 z")
		.room(:style="{'grid-area': `1 / 1 / auto / auto`}")
		.room(v-for="(room, index) of rooms", :style="{'grid-area': `1 / ${index + 2 } / auto / auto`}") {{ getLocalizedString(room.name) }}
			bunt-button.room-description(v-if="getLocalizedString(room.description)", :tooltip="getLocalizedString(room.description)", tooltip-placement="bottom-end") ?
		.room(v-if="hasSessionsWithoutRoom", :style="{'grid-area': `1 / ${rooms.length + 2} / auto / -1`}") no location
		template(v-for="session of sessions")
			session(
				v-if="isProperSession(session)",
				:session="session",
				:style="getSessionStyle(session)",
				:showAbstract="false", :showRoom="false",
				:faved="favs.includes(session.id)",
				:hasAmPm="hasAmPm",
				@fav="$emit('fav', session.id)",
				@unfav="$emit('unfav', session.id)"
			)
			.break(v-else, :style="getSessionStyle(session)")
				.time-box
					.start(v-if="hasAmPm", class="has-ampm")
						.time {{ session.start.format('h:mm') }}
						.ampm {{ session.start.format('A') }}
					.start(v-else)
						.time {{ session.start.format('LT') }}
					.duration {{ getPrettyDuration(session.start, session.end) }}
					.buffer
				.info
					.title {{ getLocalizedString(session.title) }}
</template>
<script>
// TODO
// - handle click on already selected day (needs some buntpapier hacking)
// - optionally only show venueless rooms
import moment from 'moment-timezone'
import Session from './Session'
import { getLocalizedString, getPrettyDuration } from 'views/schedule/utils'

const getSliceName = function(date) {
	return `slice-${date.format('MM-DD-HH-mm')}`
}

export default {
	components: { Session },
	emits: ['fav', 'unfav', 'changeDay'],
	props: {
		sessions: Array,
		rooms: Array,
		favs: {
			type: Array,
			default() {
				return []
			}
		},
		currentDay: Object,
		now: Object,
		scrollParent: Element
	},
	data() {
		return {
			moment,
			getLocalizedString,
			getPrettyDuration,
			scrolledDay: null
		}
	},
	computed: {
		hasSessionsWithoutRoom() {
			return this.sessions.some(s => !s.room)
		},
		hasAmPm() {
			return moment.localeData().longDateFormat('LT').endsWith(' A')
		},
		timeslices() {
			const minimumSliceMins = 30
			const slices = []
			const slicesLookup = {}
			const pushSlice = function(date, {hasSession = false, hasBreak = false, hasStart = false, hasEnd = false} = {}) {
				const name = getSliceName(date)
				let slice = slicesLookup[name]
				if (slice) {
					slice.hasSession = slice.hasSession || hasSession
					slice.hasBreak = slice.hasBreak || hasBreak
					slice.hasStart = slice.hasStart || hasStart
					slice.hasEnd = slice.hasEnd || hasEnd
				} else {
					slice = {
						date,
						name,
						hasSession,
						hasBreak,
						hasStart,
						hasEnd,
						datebreak: date.isSame(date.clone().startOf('day'))
					}
					slices.push(slice)
					slicesLookup[name] = slice
				}
			}
			const fillHalfHours = function(start, end, {hasSession, hasBreak} = {}) {
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
				halfHourSlices.forEach(slice => pushSlice(slice, {hasSession, hasBreak}))
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

				const isProper = this.isProperSession(session)
				// add start and end slices for the session itself
				pushSlice(session.start, {hasSession: isProper, hasBreak: !isProper, hasStart: true})
				pushSlice(session.end, {hasEnd: true})
				// add half hour slices between a session
				fillHalfHours(session.start, session.end, {hasSession: isProper, hasBreak: !isProper})
			}

			const sliceIsFraction = function(slice) {
				if (!slice) return
				return slice.date.minutes() !== 0 && slice.date.minutes() !== minimumSliceMins
			}

			const sliceShouldDisplay = function(slice, index) {
				if (!slice) return
				// keep slices with sessions or when changing dates, or when sessions start or immediately after they end
				if (slice.hasSession || slice.datebreak || slice.hasStart || slice.hasEnd) return true
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
			// remove empty gaps in slices
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
			// Only count slice as gap if it is longer than 30 minutes
			compactedSlices.forEach((slice, index) => {
				if (slice.gap && index < compactedSlices.length - 1) {
					if (compactedSlices[index + 1].date.diff(slice.date, 'minutes') <= 30) slice.gap = false
				}
			})
			// remove gap at the end of the schedule
			if (compactedSlices && compactedSlices[compactedSlices.length - 1]?.gap) compactedSlices.pop()
			return compactedSlices
		},
		visibleTimeslices() {
			return this.timeslices.filter(slice => slice.date.minute() % 30 === 0)
		},
		gridStyle() {
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
		nowSlice() {
			let slice
			for (const s of this.timeslices) {
				if (this.now.isBefore(s.date)) {
					break
				}
				slice = s
			}
			if (slice) {
				const nextSlice = this.timeslices[this.timeslices.indexOf(slice) + 1]
				if (!nextSlice) {
					return null
				}
				// is on daybreak
				if (nextSlice.date.diff(slice.date, 'minutes') > 30) {
					return {
						slice: nextSlice,
						offset: 0,
						onDaybreak: true
					}
				}
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
	async mounted() {
		await this.$nextTick()
		this.observer = new IntersectionObserver(this.onIntersect, {
			root: this.scrollParent,
			rootMargin: '-45% 0px'
		})
		for (const [ref, el] of Object.entries(this.$refs)) {
			if (!ref.startsWith('slice') || !ref.endsWith('00-00')) continue
			this.observer.observe(el[0])
		}
		// scroll to now, unless URL overrides now
		let fragmentIsDate = false
		const fragment = window.location.hash.slice(1)
		if (fragment && fragment.length === 10) {
			const initialDay = moment(fragment, 'YYYY-MM-DD')
			if (initialDay) {
				fragmentIsDate = true
			}
		}
		if (fragmentIsDate || !this.$refs.now) return
		const scrollTop = this.$refs.now.offsetTop + this.getOffsetTop() - 90
		if (this.scrollParent && typeof this.scrollParent.scrollTo === 'function') {
			this.scrollParent.scrollTo({ top: scrollTop })
		} else {
			window.scroll({top: scrollTop})
		}
	},
	methods: {
		isProperSession(session) {
			// breaks and such don't have ids
			return !!session.id
		},
		getSessionStyle(session) {
			const roomIndex = this.rooms.indexOf(session.room)
			return {
				'grid-row': `${getSliceName(session.start)} / ${getSliceName(session.end)}`,
				'grid-column': roomIndex > -1 ? roomIndex + 2 : null
			}
		},
		getOffsetTop() {
			const rect = this.$parent.$el.getBoundingClientRect()
			return rect.top + window.scrollY
		},
		getSliceClasses(slice) {
			return {
				datebreak: slice.datebreak,
				gap: slice.gap
			}
		},
		getSliceStyle(slice) {
			if (slice.datebreak) {
				let index = this.timeslices.findIndex(s => s.date.isAfter(slice.date, 'day'))
				if (index < 0) {
					index = this.timeslices.length - 1
				}
				return {'grid-area': `${slice.name} / 1 / ${this.timeslices[index].name} / auto`}
			}
			return {'grid-area': `${slice.name} / 1 / auto / auto`}
		},
		getSliceLabel(slice) {
			if (slice.datebreak) return slice.date.format('ddd[\n]DD. MMM')
			return slice.date.format('LT')
		},
		changeDay(day) {
			if (this.scrolledDay === day) return
			const el = this.$refs[getSliceName(day)]?.[0]
			if (!el) return
			const offset = el.offsetTop + this.getOffsetTop()
			if (this.scrollParent && typeof this.scrollParent.scrollTo === 'function') {
				this.scrollParent.scrollTo({ top: offset })
			} else {
				window.scroll({top: offset})
			}
		},
		onIntersect(entries) {
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
	background-color: $clr-grey-50
	.grid
		display: grid
		grid-template-columns: 78px repeat(var(--total-rooms), 1fr) auto
		// grid-gap: 8px
		position: relative
		min-width: min-content
		> .room
			position: sticky
			top: calc(var(--pretalx-sticky-date-offset) + var(--pretalx-sticky-top-offset, 0px))
			display: flex
			justify-content: center
			align-items: center
			font-size: 18px
			background-color: $clr-white
			border-bottom: border-separator()
			z-index: 20
			.room-description
				border: 2px solid $clr-grey-400
				border-radius: 100%
				height: 20px
				width: 20px
				padding: 0
				font-weight: bold
				min-width: 0
				button-style(color: $clr-white, text-color: $clr-grey-500)
				margin-left: 8px
				.bunt-tooltip
					height: auto
					width: 200px
					white-space: normal
		.break
			.time-box
				background-color: $clr-grey-500
				.start
					color: $clr-primary-text-dark
				.duration
					color: $clr-secondary-text-dark
			.info
				background-color: $clr-grey-200
				border: none
				justify-content: center
				align-items: center
				.title
					font-size: 20px
					font-weight: 500
					color: $clr-secondary-text-light
					align: center
	.timeslice
		color: $clr-secondary-text-light
		padding: 8px 10px 0 16px
		white-space: nowrap
		position: sticky
		left: 0
		text-align: center
		background-color: $clr-grey-50
		border-top: 1px solid $clr-dividers-light
		z-index: 20
		&.datebreak
			font-weight: 600
			border-top: 3px solid $clr-dividers-light
			white-space: pre
		&.gap
			&::before
				content: ''
				display: block
				width: 6px
				height: calc(100% - 30px - 12px)
				position: absolute
				top: 30px
				left: 50%
				background-image: radial-gradient(circle closest-side, $clr-grey-500 calc(100% - .5px), transparent 100%)
				background-position: 0 0
				background-size: 5px 15px
				background-repeat: repeat-y

	.timeline
		height: 1px
		background-color: $clr-dividers-light
		position: absolute
		width: 100%
		&.datebreak
			height: 3px
	.now
		z-index: 20
		position: sticky
		left: 2px
		&::before
			content: ''
			display: block
			height: 2px
			background-color: $clr-red
			position: absolute
			top: calc(var(--offset) * 100%)
			width: 100%
		&.on-daybreak::before
			background: repeating-linear-gradient(to right, transparent, transparent 5px, $clr-red 5px, $clr-red 10px)
		svg
			position: absolute
			top: calc(var(--offset) * 100% - 11px)
			height: 24px
			width: 24px
			fill: $clr-red
	.bunt-scrollbar-rail-wrapper-x, .bunt-scrollbar-rail-wrapper-y
		z-index: 30
</style>

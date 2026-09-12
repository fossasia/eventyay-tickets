<template lang="pug">
.c-grid-schedule(:class="[('density-' + density), { 'is-shift-mode': isShiftMode }]")
	.sticky-header
		.rooms-bar(ref="roomsBar")
			.rooms-inner(:style="roomsBarStyle")
				.room
				.room(v-for="(room, index) of rooms", :key="room.id || index", :style="isShiftMode ? getRoomHeaderStyle(room) : {}")
					span.room-name(:title="getLocalizedString(room.name)") {{ getLocalizedString(room.name) }}
					span.room-description(v-if="getLocalizedString(room.description)", @mouseenter="showRoomTooltip($event, room)", @mouseleave="hideRoomTooltip") ?
				.room(v-if="hasSessionsWithoutRoom") no location
		.room-tooltip(v-if="roomTooltip.visible", :style="roomTooltipStyle") {{ roomTooltip.text }}
		.custom-scrollbar(ref="customScrollbar", v-show="scrollThumbWidth > 0 && scrollThumbWidth < 100")
			.scroll-track(ref="scrollTrack", @mousedown="onTrackClick")
				.scroll-thumb(ref="scrollThumb", :style="{'width': scrollThumbWidth + '%', 'left': scrollThumbLeft + '%'}", @mousedown.stop="onThumbMousedown")
	.grid-viewport(ref="gridViewport", @scroll="onViewportScroll")
		.grid(:style="gridStyle")
			template(v-for="slice of visibleTimeslices")
				.timeslice(:ref="slice.name", :class="getSliceClasses(slice)", :data-slice-day="slice.date.clone().tz(timezone).format('YYYY-MM-DD')", :style="getSliceStyle(slice)") {{ getSliceLabel(slice) }}
				.timeline(:class="getSliceClasses(slice)", :style="getSliceStyle(slice)")
			.now(v-if="nowSlice", ref="now", :class="{'on-daybreak': nowSlice.onDaybreak}", :style="{'grid-area': `${nowSlice.slice.name} / 1 / auto / auto`, '--offset': nowSlice.offset}")
				svg(viewBox="0 0 10 10", :title="nowHoverTime")
					path(d="M 0 0 L 10 5 L 0 10 z")
			template(v-for="session of sessions")
				component(
					:is="SessionComponent",
					v-if="isProperSession(session)",
					:session="session",
					:now="now",
					:locale="locale",
					:timezone="timezone",
					:style="getSessionStyle(session)",
					:showAbstract="false", :showRoom="false",
					:showSessionType="true",
					:showFavCount="showFavCount",
					:faved="favSet.has(session.id)",
					:hasAmPm="hasAmPm",
					:onHomeServer="onHomeServer",
					@fav="$emit('fav', session.id)",
					@unfav="$emit('unfav', session.id)"
				)
				grid-break(
					v-else,
					:session="session",
					:timezone="timezone",
					:hasAmPm="hasAmPm",
					:style="getSessionStyle(session)"
				)
	.print-grids
		template(v-for="(chunk, chunkIdx) of printRoomChunks", :key="chunkIdx")
			.print-chunk
				.print-rooms-bar(:style="{'--total-rooms': chunk.length}")
					.room
					.room(v-for="(room, index) of chunk", :key="room.id || index")
						span.room-name {{ getLocalizedString(room.name) }}
				.print-grid(:style="getPrintChunkGridStyle(chunk)")
					template(v-for="slice of visibleTimeslices")
						.timeslice(:class="getSliceClasses(slice)", :style="getSliceStyle(slice)") {{ getSliceLabel(slice) }}
						.timeline(:class="getSliceClasses(slice)", :style="getSliceStyle(slice)")
					template(v-for="session of getChunkSessions(chunk)")
						component(
							:is="SessionComponent",
							v-if="isProperSession(session)",
							:session="session",
							:now="now",
							:locale="locale",
							:timezone="timezone",
							:style="getChunkSessionStyle(session, chunk)",
							:showAbstract="false", :showRoom="false",
							:showSessionType="true",
							:showFavCount="showFavCount",
							:faved="favSet.has(session.id)",
							:hasAmPm="hasAmPm",
							:onHomeServer="onHomeServer",
							@fav="$emit('fav', session.id)",
							@unfav="$emit('unfav', session.id)"
						)
						grid-break(
							v-else,
							:session="session",
							:timezone="timezone",
							:hasAmPm="hasAmPm",
							:style="getChunkSessionStyle(session, chunk)"
						)
</template>
<script>
// TODO
// - handle click on already selected day (needs some buntpapier hacking)
// - optionally only show venueless rooms
import moment from 'moment-timezone'
import TalkSession from './Session'
import ShiftSession from '../teamshifts-adapter/Session.vue'
import GridBreak from './GridBreak'
import { getLocalizedString } from '../utils'
import { isShiftSchedule, computeShiftOverlapPlacement, computeShiftColumnLayout, buildShiftGridTemplateColumns } from '../teamshifts-adapter'

const getSliceName = function (date) {
	return `slice-${date.format('MM-DD-HH-mm')}`
}

export default {
	components: { TalkSession, ShiftSession, GridBreak },
	props: {
		sessions: Array,
		rooms: Array,
		favs: {
			type: Array,
			default () {
				return []
			}
		},
		currentDay: String,
		forceScrollDay: { type: Number, default: 0 },
		now: Object,
		timezone: String,
		locale: String,
		hasAmPm: Boolean,
		scrollParent: Element,
		onHomeServer: Boolean,
		showFavCount: {
			type: Boolean,
			default: false
		},
		disableAutoScroll: Boolean,
		density: {
			type: String,
			default: 'default'
		},
		timeDensityMinutes: {
			type: Number,
			default: 30
		}
	},
	inject: {
		scheduleData: { default: null },
		translationMessages: { default: () => ({}) }
	},
	data () {
		return {
			getLocalizedString,
			scrollContentWidth: 0,
			scrollThumbWidth: 100,
			scrollThumbLeft: 0,
			_scrollDayUpdate: false,
			_scrollSource: null,
			_thumbDrag: null,
			roomTooltip: { visible: false, text: '', x: 0, y: 0 }
		}
	},
	computed: {
		SessionComponent () {
			const data = this.scheduleData?.value ?? this.scheduleData
			return isShiftSchedule(data) ? ShiftSession : TalkSession
		},
		isShiftMode () {
			const data = this.scheduleData?.value ?? this.scheduleData
			return isShiftSchedule(data)
		},
		favSet () {
			return new Set(this.favs || [])
		},
		/** Precompute datebreak row span targets; avoids O(n) findIndex per datebreak slice in getSliceStyle. */
		datebreakGridEndRowByName () {
			const ts = this.timeslices
			if (!ts.length) return {}
			const out = Object.create(null)
			let j = 0
			for (let i = 0; i < ts.length; i++) {
				if (!ts[i].datebreak) continue
				const d0 = ts[i].date.clone().startOf('day').valueOf()
				while (j < ts.length && ts[j].date.clone().startOf('day').valueOf() <= d0) j++
				const endIdx = j < ts.length ? j : ts.length - 1
				out[ts[i].name] = ts[endIdx].name
			}
			return out
		},
		roomsBarStyle () {
			if (this.isShiftMode) {
				const minWidth = '420px'
				const cols = buildShiftGridTemplateColumns(this.rooms, this.sessions, minWidth)
				return {
					'grid-template-columns': cols,
					'min-width': this.scrollContentWidth ? (this.scrollContentWidth + 'px') : null,
				}
			}
			return {
				'--total-rooms': this.rooms.length,
				'min-width': this.scrollContentWidth ? (this.scrollContentWidth + 'px') : null,
			}
		},
		roomIndexLookup () {
			const m = new Map()
			this.rooms.forEach((room, i) => m.set(room, i))
			return m
		},
		nowHoverTime () {
			if (!this.now || !this.timezone) return ''
			const zonedNow = this.now.clone().tz(this.timezone)
			return this.hasAmPm ? zonedNow.format('h:mm A') : zonedNow.format('HH:mm')
		},
		hasSessionsWithoutRoom () {
			return this.sessions.some(s => !s.room)
		},
		printRoomChunks () {
			const chunkSize = 4
			const chunks = []
			for (let i = 0; i < this.rooms.length; i += chunkSize) {
				chunks.push(this.rooms.slice(i, i + chunkSize))
			}
			return chunks.length ? chunks : [this.rooms]
		},
		timeslices () {
			const minimumSliceMins = this.timeDensityMinutes || 30
			const slices = []
			const slicesLookup = {}
			const pushSlice = function (date, {hasSession = false, hasBreak = false, hasStart = false, hasEnd = false} = {}) {
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
						datebreak: date.valueOf() === date.clone().startOf('day').valueOf()
					}
					slices.push(slice)
					slicesLookup[name] = slice
				}
			}
			const fillHalfHours = function (start, end, {hasSession, hasBreak} = {}) {
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
				} else if (session.start.isAfter(lastSlice.date)) {
					fillHalfHours(lastSlice.date, session.start)
				}

				const isProper = this.isProperSession(session)
				// add start and end slices for the session itself
				pushSlice(session.start, {hasSession: isProper, hasBreak: !isProper, hasStart: true})
				pushSlice(session.end, {hasEnd: true})
				// add half hour slices between a session
				fillHalfHours(session.start, session.end, {hasSession: isProper, hasBreak: !isProper})
			}

			const sliceIsFraction = function (slice) {
				if (!slice) return
				return slice.date.minute() % minimumSliceMins !== 0
			}

			const sliceShouldDisplay = function (slice, index) {
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
			// Only count slice as gap if it is longer than the base interval
			compactedSlices.forEach((slice, index) => {
				if (slice.gap && index < compactedSlices.length - 1) {
					if (compactedSlices[index + 1].date.diff(slice.date, 'minutes') <= minimumSliceMins) slice.gap = false
				}
			})
			// remove gap at the end of the schedule
			if (compactedSlices[compactedSlices.length - 1]?.gap) compactedSlices.pop()
			for (let i = 0; i < compactedSlices.length; i++) {
				const next = compactedSlices[i + 1]
				if (next?.datebreak || !next) {
					compactedSlices[i].dayEnd = true
				}
			}
			return compactedSlices
		},
		visibleTimeslices () {
			const minimumSliceMins = this.timeDensityMinutes || 30
			return this.timeslices.filter(slice => slice.date.minute() % minimumSliceMins === 0)
		},
		gridStyle () {
			const scale = this.density === 'compact' ? 0.65 : this.density === 'comfortable' ? 1.4 : 1
			const minimumSliceMins = this.timeDensityMinutes || 30
			const baseSliceHeight = 60 * (minimumSliceMins / 30)
			let rows = ''
			rows += this.timeslices.map((slice, index) => {
				const next = this.timeslices[index + 1]
				let height = baseSliceHeight
				if (slice.gap) {
					height = 100 * (minimumSliceMins / 30)
			} else if (slice.datebreak) {
					height = 36 * (minimumSliceMins / 30)
				} else if (next) {
					height = Math.min(baseSliceHeight, next.date.diff(slice.date, 'minutes') * 2)
				}
				height = Math.round(height * scale)
				return `[${slice.name}] minmax(${height}px, auto)`
			}).join(' ')
			if (this.isShiftMode) {
				const minWidth = getComputedStyle(this.$el || document.documentElement)
					.getPropertyValue('--room-col-min').trim() || '420px'
				return {
					'grid-template-columns': buildShiftGridTemplateColumns(this.rooms, this.sessions, minWidth),
					'grid-template-rows': rows,
				}
			}
			return {
				'--total-rooms': this.rooms.length,
				'grid-template-rows': rows
			}
		},
		nowSlice () {
			const minimumSliceMins = this.timeDensityMinutes || 30
			let slice
			let sliceIdx = -1
			for (let i = 0; i < this.timeslices.length; i++) {
				const s = this.timeslices[i]
				if (this.now.isBefore(s.date)) break
				slice = s
				sliceIdx = i
			}
			if (slice) {
				const nextSlice = this.timeslices[sliceIdx + 1]
				if (!nextSlice) return null
				// is on daybreak
				if (nextSlice.date.diff(slice.date, 'minutes') > minimumSliceMins) return {
					slice: nextSlice,
					offset: 0,
					onDaybreak: true
				}
				return {
					slice,
					offset: this.now.diff(slice.date, 'minutes') / nextSlice.date.diff(slice.date, 'minutes')
				}
			}
			return null
		},
		roomTooltipStyle () {
			return {
				left: this.roomTooltip.x + 'px',
				top: this.roomTooltip.y + 'px'
			}
		}
	},
	watch: {
		currentDay (day) {
			// Only scroll when triggered by toolbar click, not by scroll-based observer
			if (this._scrollDayUpdate) {
				this._scrollDayUpdate = false
				return
			}
			this.scrollToDayStart(day)
		},
		forceScrollDay () {
			this.scrollToDayStart(this.currentDay)
		}
	},
	async mounted () {
		this.observer = new IntersectionObserver(this.onIntersect, {
			root: this.scrollParent,
			rootMargin: '-45% 0px'
		})
		for (const [ref, el] of Object.entries(this.$refs)) {
			if (!ref.startsWith('slice') || !ref.endsWith('00-00')) continue
			this.observer.observe(el[0])
		}
		await this.$nextTick()
		this.initScrollSync()
		if (!this.$refs.now) return
		if (this.disableAutoScroll) return
		const today = this.now.clone().tz(this.timezone).format('YYYY-MM-DD')
		if (this.currentDay !== today) return // Auto-scroll does not trigger when viewing a non-current day
		await new Promise(resolve => requestAnimationFrame(resolve))
		this.scrollToNow()
	},
	beforeUnmount () {
		if (this._gridResizeObserver) {
			this._gridResizeObserver.disconnect()
		}
	},
	methods: {
		isProperSession (session) {
			// breaks and such don't have ids
			return !!session.id
		},
		getRoomHeaderStyle (room) {
			const layout = computeShiftColumnLayout(this.rooms, this.sessions)
			const roomLayout = layout.get(room)
			if (!roomLayout) return {}
			return {
				'grid-column': `${roomLayout.colStart} / ${roomLayout.colStart + roomLayout.colSpan}`,
			}
		},
		getChunkSessions (chunkRooms) {
			const chunkSet = new Set(chunkRooms)
			return this.sessions.filter(s => {
				if (!this.isProperSession(s)) {
					return !s.room || chunkSet.has(s.room)
				}
				return chunkSet.has(s.room)
			})
		},
		getChunkSessionStyle (session, chunkRooms) {
			const roomIndex = chunkRooms.indexOf(session.room)
			const gridRow = `${getSliceName(session.start)} / ${getSliceName(session.end)}`
			if (roomIndex > -1) {
				return { 'grid-row': gridRow, 'grid-column': roomIndex + 2 }
			}
			return { 'grid-row': gridRow, 'grid-column': `2 / ${chunkRooms.length + 2}` }
		},
		getPrintChunkGridStyle (chunk) {
			const rows = this.timeslices.map((slice, index) => {
				const next = this.timeslices[index + 1]
				let height = 60
				if (slice.gap) {
					height = 100
				} else if (slice.datebreak) {
					height = 36
				} else if (next) {
					height = Math.min(60, next.date.diff(slice.date, 'minutes') * 2)
				}
				return `[${slice.name}] minmax(${height}px, auto)`
			}).join(' ')
			return {
				'--total-rooms': chunk.length,
				'grid-template-rows': rows
			}
		},
		getSessionStyle (session) {
			const roomIndex = this.roomIndexLookup.has(session.room) ? this.roomIndexLookup.get(session.room) : -1
			const data = this.scheduleData?.value ?? this.scheduleData
			if (isShiftSchedule(data) && session.start && session.end) {
				const columnLayout = computeShiftColumnLayout(this.rooms, this.sessions)
				const placement = computeShiftOverlapPlacement(session, this.sessions, columnLayout)
				if (placement) {
					return {
						'grid-row': placement.gridRow,
						'grid-column': placement.gridColumn,
					}
				}
				const layout = columnLayout.get(session.room)
				const col = layout ? layout.colStart : (roomIndex > -1 ? roomIndex + 2 : null)
				return {
					'grid-row': `${getSliceName(session.start)} / ${getSliceName(session.end)}`,
					'grid-column': col,
				}
			}
			return {
				'grid-row': `${getSliceName(session.start)} / ${getSliceName(session.end)}`,
				'grid-column': roomIndex > -1 ? roomIndex + 2 : null
			}
		},
		getStickyHeaderClearance () {
			const stickyHeader = this.$el.querySelector('.sticky-header')
			const scheduleRoot = this.$el.closest('.pretalx-schedule') || this.$el.closest('.c-schedule-view')
			const toolbar = scheduleRoot?.querySelector('.c-schedule-toolbar')
			let stickyTopOffset = 40
			if (scheduleRoot) {
				const parsed = parseFloat(getComputedStyle(scheduleRoot).getPropertyValue('--pretalx-sticky-top-offset'))
				if (Number.isFinite(parsed)) stickyTopOffset = parsed
			}
			let toolbarHeight = 0
			if (toolbar) {
				toolbarHeight = toolbar.getBoundingClientRect().height
			} else if (scheduleRoot) {
				const parsed = parseFloat(getComputedStyle(scheduleRoot).getPropertyValue('--pretalx-toolbar-height'))
				toolbarHeight = Number.isFinite(parsed) ? parsed : 0
			}
			const stickyHeaderHeight = stickyHeader ? stickyHeader.getBoundingClientRect().height : 0
			let versionWarning = 0
			if (scheduleRoot) {
				const vh = parseFloat(getComputedStyle(scheduleRoot).getPropertyValue('--pretalx-version-warning-height'))
				versionWarning = Number.isFinite(vh) ? vh : 0
			}
			return stickyTopOffset + toolbarHeight + stickyHeaderHeight + versionWarning + 6
		},
		getScrolledDay () {
			// go through all timeslices, on the first one that is actually visible in current scroll, return its date
			for (const slice of this.timeslices) {
				const el = this.$refs[slice.name]?.[0]
				if (!el) continue
				const rect = el.getBoundingClientRect()
				// only count as visible if at least 100px are visible
				const buffer = 100
				if (rect.top + buffer < window.innerHeight && rect.bottom - buffer > 0) {
					return slice.date
				}
			}
		},
		getSliceClasses (slice) {
			return {
				datebreak: slice.datebreak,
				gap: slice.gap,
				'day-end': slice.dayEnd
			}
		},
		getSliceStyle (slice) {
			if (slice.datebreak) {
				const endName = this.datebreakGridEndRowByName[slice.name]
				if (endName) {
					return {'grid-area': `${slice.name} / 1 / ${endName} / auto`}
				}
				let index = this.timeslices.findIndex(s => s.date.clone().startOf('day').isAfter(slice.date.clone().startOf('day')))
				if (index < 0) index = this.timeslices.length - 1
				return {'grid-area': `${slice.name} / 1 / ${this.timeslices[index].name} / auto`}
			}
			return {'grid-area': `${slice.name} / 1 / auto / auto`}
		},
		getSliceLabel (slice) {
			if (slice.datebreak) {
				const date = slice.date
				return date.format('ddd') + '\n' + date.format('D MMM')
			}
			return slice.date.clone().tz(this.timezone).format('h:mm A')
		},
		changeDay (day) {
			this.scrollToDayStart(day)
		},
		scrollElementIntoViewWithClearance (el) {
			if (!el) return
			const clearance = this.getStickyHeaderClearance()
			const rect = el.getBoundingClientRect()
			const scrollEl = this.scrollParent
			const isWindowScroll = !scrollEl || scrollEl === document.documentElement || scrollEl === document.body
			if (!isWindowScroll) {
				const parentRect = scrollEl.getBoundingClientRect()
				const delta = rect.top - parentRect.top - clearance
				scrollEl.scrollTop += delta
			} else {
				window.scrollBy({ top: rect.top - clearance })
			}
		},
		scrollToNow() {
			if (!this.$refs.now) return
			this.scrollElementIntoViewWithClearance(this.$refs.now)
		},
		scrollToDayStart (day) {
			const dayStr = moment.isMoment(day) ? day.clone().tz(this.timezone).startOf('day').format('YYYY-MM-DD') : day
			const el = this.$el.querySelector(`.timeslice.datebreak[data-slice-day="${dayStr}"]`)
			if (!el) return
			this.scrollElementIntoViewWithClearance(el)
		},
		initScrollSync () {
			const viewport = this.$refs.gridViewport
			if (!viewport) return
			this.updateScrollbar()
			this._gridResizeObserver = new ResizeObserver(() => this.updateScrollbar())
			const grid = viewport.querySelector('.grid')
			if (grid) this._gridResizeObserver.observe(grid)
			setTimeout(() => this.updateScrollbar(), 200)
		},
		updateScrollbar () {
			const viewport = this.$refs.gridViewport
			if (!viewport) return
			this.scrollContentWidth = viewport.scrollWidth
			const ratio = viewport.clientWidth / viewport.scrollWidth
			this.scrollThumbWidth = Math.min(100, ratio * 100)
			const maxScroll = viewport.scrollWidth - viewport.clientWidth
			if (maxScroll > 0) {
				this.scrollThumbLeft = (viewport.scrollLeft / maxScroll) * (100 - this.scrollThumbWidth)
			} else {
				this.scrollThumbLeft = 0
			}
		},
		onViewportScroll () {
			if (this._scrollSource === 'thumb') return
			this._scrollSource = 'viewport'
			const viewport = this.$refs.gridViewport
			const roomsBar = this.$refs.roomsBar
			if (roomsBar) roomsBar.scrollLeft = viewport.scrollLeft
			this.updateScrollbar()
			requestAnimationFrame(() => { this._scrollSource = null })
		},
		onTrackClick (e) {
			const track = this.$refs.scrollTrack
			const viewport = this.$refs.gridViewport
			if (!track || !viewport) return
			const rect = track.getBoundingClientRect()
			const clickRatio = (e.clientX - rect.left) / rect.width
			const maxScroll = viewport.scrollWidth - viewport.clientWidth
			viewport.scrollLeft = clickRatio * maxScroll
			if (this.$refs.roomsBar) this.$refs.roomsBar.scrollLeft = viewport.scrollLeft
			this.updateScrollbar()
		},
		onThumbMousedown (e) {
			e.preventDefault()
			const track = this.$refs.scrollTrack
			const viewport = this.$refs.gridViewport
			if (!track || !viewport) return
			const trackRect = track.getBoundingClientRect()
			const startX = e.clientX
			const startScrollLeft = viewport.scrollLeft
			const maxScroll = viewport.scrollWidth - viewport.clientWidth
			const trackWidth = trackRect.width
			const thumbWidthPx = (this.scrollThumbWidth / 100) * trackWidth
			const scrollableTrack = trackWidth - thumbWidthPx

			const onMouseMove = (ev) => {
				this._scrollSource = 'thumb'
				const dx = ev.clientX - startX
				const scrollDelta = (dx / scrollableTrack) * maxScroll
				viewport.scrollLeft = startScrollLeft + scrollDelta
				if (this.$refs.roomsBar) this.$refs.roomsBar.scrollLeft = viewport.scrollLeft
				this.updateScrollbar()
			}
			const onMouseUp = () => {
				this._scrollSource = null
				document.removeEventListener('mousemove', onMouseMove)
				document.removeEventListener('mouseup', onMouseUp)
			}
			document.addEventListener('mousemove', onMouseMove)
			document.addEventListener('mouseup', onMouseUp)
		},
		onIntersect (entries) {
			const intersecting = entries.filter(entry => entry.isIntersecting)
			if (!intersecting.length) return
			const entry = intersecting.sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0]
			const dayStr = entry.target.dataset.sliceDay
			if (!dayStr || dayStr === this.currentDay) return
			// Only update the active day indicator — don't trigger a scroll jump.
			// scrollToDayStart is only called from toolbar clicks (selectDay / forceScrollDay).
			this._scrollDayUpdate = true
			this.$emit('changeDay', moment.tz(dayStr, this.timezone).startOf('day'))
		},
		showRoomTooltip (event, room) {
			const rect = event.target.getBoundingClientRect()
			this.roomTooltip = {
				visible: true,
				text: getLocalizedString(room.description),
				x: rect.left + rect.width / 2,
				y: rect.bottom + 6
			}
		},
		hideRoomTooltip () {
			this.roomTooltip = { visible: false, text: '', x: 0, y: 0 }
		}
	}
}
</script>
<style lang="stylus">
.c-grid-schedule
	flex: auto
	background-color: $clr-grey-50
	--room-col-min: 320px
	&.is-shift-mode
		--room-col-min: 420px
	.sticky-header
		position: sticky
		top: calc(var(--pretalx-sticky-top-offset, 0px) + var(--pretalx-toolbar-height, 30px) + var(--pretalx-version-warning-height, 0px) - 1px)
		z-index: 25
		background-color: $clr-white
	.rooms-bar
		overflow: hidden
		.rooms-inner
			display: grid
			grid-template-columns: 78px repeat(var(--total-rooms), minmax(var(--room-col-min), 1fr)) auto
			min-width: max(min-content, calc(78px + (var(--total-rooms) * var(--room-col-min)) + 60px))
			> .room
				display: flex
				justify-content: center
				align-items: center
				min-width: 0
				gap: 0.4em
				font-size: 18px
				background-color: $clr-white
				padding: 8px 4px
				.room-name
					min-width: 0
					overflow: hidden
					white-space: nowrap
					text-overflow: ellipsis
				.room-description
					display: inline-flex
					justify-content: center
					align-items: center
					border: 1px solid $clr-grey-400
					border-radius: 100%
					height: 1.1em
					width: 1.1em
					font-weight: bold
					font-size: 0.75em
					line-height: 1
					color: $clr-grey-500
					background: $clr-white
					margin-left: 0.4em
					cursor: pointer
					user-select: none
					flex-shrink: 0
	.room-tooltip
		position: fixed
		transform: translateX(-50%)
		background-color: rgba(0, 0, 0, 0.87)
		color: #fff
		padding: 6px 10px
		border-radius: 4px
		font-size: 13px
		line-height: 1.4
		max-width: 220px
		white-space: normal
		z-index: 1000
		pointer-events: none
	.custom-scrollbar
		padding: 0
		.scroll-track
			height: 3px
			background: rgba(0, 0, 0, 0.10)
			border-radius: 2px
			position: relative
			cursor: pointer
			.scroll-thumb
				position: absolute
				top: 50%
				transform: translateY(-50%)
				height: 5px
				background: var(--pretalx-clr-primary, #3b82f6)
				border-radius: 3px
				cursor: grab
				&:active
					cursor: grabbing
	.grid-viewport
		overflow-x: auto
		overflow-y: clip
		scrollbar-width: none
		&::-webkit-scrollbar
			display: none
		.grid
			display: grid
			grid-template-columns: 78px repeat(var(--total-rooms), minmax(var(--room-col-min), 1fr)) auto
			position: relative
			min-width: max(min-content, calc(78px + (var(--total-rooms) * var(--room-col-min)) + 60px))
			.c-linear-schedule-session, .c-grid-schedule-break
				margin: 6px
				min-width: 0
				box-sizing: border-box
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
			font-weight: 700
			border-top: 3px solid $clr-dividers-light
			border-bottom: 3px solid $clr-dividers-light
			white-space: pre
			padding-top: 2px
			font-size: 12px
			line-height: 1.2
			overflow: hidden
			max-height: 100%
			align-content: start
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
		&.day-end
			height: 3px
			background-color: $clr-grey-500
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
	.print-grids
		display: none

.c-grid-schedule.density-compact
	.timeslice
		padding: 4px 6px 0 10px
		font-size: 12px
	.rooms-bar .rooms-inner > .room
		font-size: 14px
		padding: 4px 2px
	.grid-viewport .grid
		.c-linear-schedule-session, .c-grid-schedule-break
			margin: 4px 3px
			min-height: 48px
			font-size: 12px
	.grid
		grid-template-columns: 60px repeat(var(--total-rooms), minmax(var(--room-col-min), 1fr)) auto
	.rooms-inner
		grid-template-columns: 60px repeat(var(--total-rooms), minmax(var(--room-col-min), 1fr)) auto

.c-grid-schedule.density-comfortable
	.timeslice
		padding: 12px 14px 0 20px
		font-size: 16px
	.rooms-bar .rooms-inner > .room
		font-size: 20px
		padding: 12px 6px
	.grid-viewport .grid
		.c-linear-schedule-session, .c-grid-schedule-break
			margin: 12px 9px
			min-height: 120px
			font-size: 15px
	.grid
		grid-template-columns: 96px repeat(var(--total-rooms), minmax(var(--room-col-min), 1fr)) auto
	.rooms-inner
		grid-template-columns: 96px repeat(var(--total-rooms), minmax(var(--room-col-min), 1fr)) auto

@media (max-width: 600px)
	.c-grid-schedule
		--room-col-min: 240px

@media print
	.c-grid-schedule
		.sticky-header
			display: none !important
		.grid-viewport
			display: none !important
		.print-grids
			display: block !important
			.print-chunk
				break-inside: avoid
				page-break-inside: avoid
				&:not(:last-child)
					page-break-after: always
				.print-rooms-bar
					display: grid
					grid-template-columns: 78px repeat(var(--total-rooms), 1fr) auto
					.room
						text-align: center
						font-size: 16px
						font-weight: 600
						padding: 8px 4px
						border-bottom: 2px solid #ccc
						min-width: 0
						.room-name
							display: block
							overflow: hidden
							white-space: nowrap
							text-overflow: ellipsis
				.print-grid
					display: grid
					grid-template-columns: 78px repeat(var(--total-rooms), 1fr) auto
					position: relative
					.c-grid-schedule-break
						.time-box
							-webkit-print-color-adjust: exact
							print-color-adjust: exact
							color-adjust: exact
						.info
							-webkit-print-color-adjust: exact
							print-color-adjust: exact
							color-adjust: exact
</style>

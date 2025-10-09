<template lang="pug">
.c-grid-schedule(ref="rootEl")
	.grid(ref="grid", :style="gridStyle", :class="gridClasses", @pointermove="updateHoverSlice($event)", @pointerup="stopDragging($event)")
		template(v-for="slice of visibleTimeslices", :key="slice.name")
			.timeslice(:ref="setTimesliceRef", :class="getSliceClasses(slice)", :data-slice="slice.date.format()", :style="getSliceStyle(slice)", @click="expandTimeslice(slice)") {{ getSliceLabel(slice) }}
				svg(viewBox="0 0 10 10", v-if="isSliceExpandable(slice)").expand
					path(d="M 0 4 L 5 0 L 10 4 z")
					path(d="M 0 6 L 5 10 L 10 6 z")
			.timeseparator(:class="getSliceClasses(slice)", :style="getSliceStyle(slice)")
		.room(:style="{'grid-area': `1 / 1 / auto / auto`}")
		.room(v-for="(room, i) of visibleRooms", :key="room.id", :style="{'grid-area': `1 / ${i + 2} / auto / auto`}")
			span {{ getLocalizedString(room.name) }}
			.hide-room.no-print(v-if="visibleRooms.length > 1", @click="hiddenRooms = rooms.filter(r => hiddenRooms.includes(r) || r === room)")
				i.fa.fa-eye-slash
		session(v-if="draggedSession && hoverSlice", :style="getHoverSliceStyle()", :session="draggedSession", :isDragClone="true", :overrideStart="hoverSlice.time")
		template(v-for="session of visibleSessions", :key="session.id")
			session(
				v-if="hasValidPosition(session)"
				:session="session",
				:warnings="session.code ? warnings[session.code] : []",
				:isDragged="draggedSession && (session.id === draggedSession.id)",
				:style="getSessionStyle(session)",
				:showRoom="false",
				@startDragging="startDragging($event)",
			)
		.availability(v-for="availability of visibleAvailabilities", :key="`${availability.room.id}-${availability.start.valueOf()}-${availability.end.valueOf()}`", :style="getSessionStyle(availability)", :class="availability.active ? ['active'] : []")
	#hiddenRooms.no-print(v-if="hiddenRooms.length")
		h4 {{ $t('Hidden rooms') }} ({{ hiddenRooms.length }})
		.room-list
			.room-entry(v-for="room of hiddenRooms", :key="room.id", @click="hiddenRooms.splice(hiddenRooms.indexOf(room), 1)")
				.span {{ getLocalizedString(room.name) }}
				.show-room(@click.stop="hiddenRooms.splice(hiddenRooms.indexOf(room), 1)")
					i.fa.fa-eye
</template>

<script lang="ts" setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import moment, { Moment } from 'moment-timezone'
import Session from './Session.vue'
import { getLocalizedString } from '~/utils'

interface Room {
  id: string
  name: string | Record<string, string>
  description?: Record<string, string>
}

interface Speaker {
  name: string
  code: string
}

interface SessionDatum {
  id: number | string
  code?: string
  title?: string | Record<string, string>
  speakers?: Speaker[]
  room: Room
  start: Moment
  end: Moment
  duration: number
  state?: string
  track?: { name: string | Record<string, string>; color?: string }
  abstract?: string
  [key: string]: string | number | boolean | Record<string, string> | Speaker[] | Room | Moment | { name: string | Record<string, string>; color?: string } | undefined
}

interface Availability {
  room: Room
  start: Moment
  end: Moment
  active?: boolean
  type?: string
  [key: string]: string | boolean | Room | Moment | undefined
}

interface Timeslice {
  date: Moment
  name: string
  hasSession?: boolean
  hasStart?: boolean
  hasEnd?: boolean
  isExpanded?: boolean
  datebreak?: boolean
  gap?: boolean
}

interface HoverSlice {
  time: Moment
  roomIndex: number
  room: Room
  duration: number
}

interface DragStartData {
  x: number
  y: number
  session: SessionDatum
  now: Moment
}

interface DragEventPayload {
  session: SessionDatum
  event: PointerEvent
}

const props = defineProps<{
  sessions: SessionDatum[]
  availabilities: {
    rooms?: Record<string, { start: string; end: string }[]>
    talks?: Record<string, { start: string; end: string }[]>
  }
  warnings: Record<string, { message: string }[]>
  start: Moment
  end: Moment
  rooms: Room[]
  currentDay: Moment | null
  draggedSession: SessionDatum | null
}>()

const emit = defineEmits([
  'startDragging',
  'editSession',
  'createSession',
  'rescheduleSession',
  'changeDay'
])

const rootEl = ref<HTMLElement | null>(null)
const grid = ref<HTMLElement | null>(null)
const scrolledDay = ref<Moment | null>(null)
const hoverSlice = ref<HoverSlice | null>(null)
const expandedTimes = ref<Moment[]>([])
const gridOffset = ref(0)
const dragScrollTimer = ref<ReturnType<typeof setInterval> | null>(null)
const dragStart = ref<DragStartData | null>(null)
const hiddenRooms = ref<Room[]>([])
const timesliceRefs = ref<HTMLElement[]>([])

let observer: IntersectionObserver | null = null

const hasValidPosition = (session: SessionDatum): boolean => {
  return !!(session.room && session.start && session.end)
}

const getSliceName = (date: Moment): string => `slice-${date.format('MM-DD-HH-mm')}`

const hoverSliceLegal = computed(() => {
  if (!hoverSlice.value || !hoverSlice.value.room || !props.draggedSession) return false
  const start = hoverSlice.value.time
  const end = hoverSlice.value.time.clone().add(props.draggedSession.duration, 'm')
  const sessionId = props.draggedSession.id
  const roomId = hoverSlice.value.room.id

  for (const session of props.sessions.filter(s => s.start)) {
    if (session.room.id === roomId && session.id !== sessionId) {
      if (
        session.start.isSame(start) ||
        session.end.isSame(end) ||
        session.start.isBetween(start, end) ||
        session.end.isBetween(start, end) ||
        start.isBetween(session.start, session.end) ||
        end.isBetween(session.start, session.end)
      ) return false
    }
  }
  return true
})

const hoverEndSlice = computed((): Moment | null => {
  if (props.draggedSession && hoverSlice.value) {
    return hoverSlice.value.time.clone().add(props.draggedSession.duration, 'm')
  }
  return null
})

const timeslices = computed<Timeslice[]>(() => {
  const minimumSliceMins = 30
  const slices: Timeslice[] = []
  const slicesLookup: Record<string, Timeslice> = {}

  const pushSlice = (
    date: Moment,
    params: Partial<Pick<Timeslice, 'hasStart' | 'hasEnd' | 'hasSession' | 'isExpanded'>> = {}
  ) => {
    const name = getSliceName(date)
    let slice = slicesLookup[name]
    if (slice) {
      slice.hasSession = slice.hasSession || !!params.hasSession
      slice.hasStart = slice.hasStart || !!params.hasStart
      slice.hasEnd = slice.hasEnd || !!params.hasEnd
      slice.isExpanded = slice.isExpanded || !!params.isExpanded
    } else {
      slice = {
        date,
        name,
        hasSession: !!params.hasSession,
        hasStart: !!params.hasStart,
        hasEnd: !!params.hasEnd,
        isExpanded: !!params.isExpanded,
        datebreak: date.isSame(date.clone().startOf('day')),
      }
      slices.push(slice)
      slicesLookup[name] = slice
    }
  }

  const fillHalfHours = (start: Moment, end: Moment, { hasSession }: { hasSession?: boolean } = {}) => {
    let mins = end.diff(start, 'minutes')
    const startingMins = minimumSliceMins - (start.minute() % minimumSliceMins)
    const halfHourSlices: Moment[] = []

    if (startingMins && startingMins !== minimumSliceMins) {
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

    const lastSlice = halfHourSlices.pop()
    halfHourSlices.forEach(slice => pushSlice(slice!, { hasSession }))
    if (lastSlice) pushSlice(lastSlice)
  }

  for (const session of props.sessions) {
    const lastSlice = slices[slices.length - 1]

    if (!lastSlice) {
      pushSlice(session.start.clone().startOf('day'))
    } else if (session.start.isAfter(lastSlice.date, 'minutes')) {
      fillHalfHours(lastSlice.date, session.start)
    }

    pushSlice(session.start, { hasStart: true, hasSession: true })
    pushSlice(session.end, { hasEnd: true })
    fillHalfHours(session.start, session.end, { hasSession: true })
  }

  for (const slice of expandedTimes.value) {
    pushSlice(slice, { isExpanded: true })
  }

  fillHalfHours(props.start, props.end)

  if (hoverEndSlice.value) pushSlice(hoverEndSlice.value, { hasEnd: true })

  const sliceIsFraction = (slice?: Timeslice): boolean => {
    if (!slice) return false
    return slice.date.minutes() !== 0 && slice.date.minutes() !== minimumSliceMins
  }

  const sliceShouldDisplay = (slice?: Timeslice, index?: number): boolean => {
    if (!slice || index === undefined) return false
    if (slice.hasSession || slice.datebreak || slice.hasStart || slice.hasEnd || slice.isExpanded) return true
    if (slice.date.hour() >= 9 && slice.date.hour() < 19) return true

    const prevSlice = slices[index - 1]
    const nextSlice = slices[index + 1]

    if (sliceIsFraction(slice)) return true
    if (
      ((prevSlice?.hasSession || (prevSlice as any)?.hasBreak || prevSlice?.hasEnd) && sliceIsFraction(prevSlice)) ||
      ((nextSlice?.hasSession || (nextSlice as any)?.hasBreak) && sliceIsFraction(nextSlice)) ||
      ((!nextSlice?.hasSession || !(nextSlice as any)?.hasBreak) && (slice.hasSession || (slice as any).hasBreak) && sliceIsFraction(nextSlice))
    ) return true
    if ((prevSlice as any)?.hasBreak && (slice as any).hasBreak) return false
    return false
  }

  slices.sort((a, b) => a.date.diff(b.date))
  const compactedSlices: Timeslice[] = []

  for (const [index, slice] of slices.entries()) {
    if (sliceShouldDisplay(slice, index)) {
      compactedSlices.push(slice)
      continue
    }

    const prevSlice = slices[index - 1]
    if (sliceShouldDisplay(prevSlice, index - 1) && !prevSlice.datebreak) {
      prevSlice.gap = true
    }
  }

  return compactedSlices
})

const oddTimeslices = computed<Moment[]>(() => {
  const result: Moment[] = []
  props.sessions.forEach(session => {
    if (session.start.minute() % 30 !== 0) result.push(session.start)
    if (session.end.minute() % 30 !== 0) result.push(session.end)
  })
  // Remove duplicates by stringifying dates (safe as moment objects)
  return [...new Set(result.map(m => m.format()))].map(f => moment(f))
})

const visibleTimeslices = computed<Timeslice[]>(() => {
  return timeslices.value.filter(slice =>
    slice.date.minute() % 30 === 0 ||
    expandedTimes.value.some(et => et.isSame(slice.date)) ||
    oddTimeslices.value.some(ot => ot.isSame(slice.date))
  )
})

const gridStyle = computed(() => {
  let rows = '[header] 52px '
  rows += timeslices.value.map((slice, index) => {
    const next = timeslices.value[index + 1]
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
    '--total-rooms': visibleRooms.value.length.toString(),
    'grid-template-rows': rows,
  }
})

const gridClasses = computed(() => {
  const result: string[] = []
  if (props.draggedSession) result.push('is-dragging')
  if (hoverSlice.value && props.draggedSession && !hoverSliceLegal.value) result.push('illegal-hover')
  return result
})

const availabilitySlices = computed<Availability[]>(() => {
  const avails: Availability[] = []
  if (!visibleTimeslices.value.length) return avails
  const earliestStart = visibleTimeslices.value[0].date
  const latestEnd = visibleTimeslices.value[visibleTimeslices.value.length - 1].date
  const draggedAvails: Array<{ start: Moment; end: Moment }> = []

  if (props.draggedSession && props.availabilities.talks?.[props.draggedSession.id as any]) {
    for (const avail of props.availabilities.talks[props.draggedSession.id as any]) {
      draggedAvails.push({
        start: moment(avail.start),
        end: moment(avail.end),
      })
    }
  }

  for (const room of visibleRooms.value) {
    if (!props.availabilities.rooms?.[room.id] || !props.availabilities.rooms[room.id].length) {
      avails.push({ room, start: earliestStart, end: latestEnd })
    } else {
      for (const avail of props.availabilities.rooms[room.id]) {
        avails.push({
          room,
          start: moment(avail.start),
          end: moment(avail.end),
        })
      }
    }

    for (const avail of draggedAvails) {
      avails.push({
        room,
        start: avail.start,
        end: avail.end,
        active: true,
      })
    }
  }

  return avails
})

const scrollParent = computed<HTMLElement | null>(() => rootEl.value?.parentElement ?? null)

const staticOffsetTop = computed(() => {
  if (!rootEl.value?.parentElement) return 0
  const rect = rootEl.value.parentElement.getBoundingClientRect()
  return rect.top
})

const visibleRooms = computed(() => {
  return props.rooms.filter(room => !hiddenRooms.value.includes(room))
})

const visibleSessions = computed(() => {
  return props.sessions.filter(session => !hiddenRooms.value.includes(session.room))
})

const visibleAvailabilities = computed(() => {
  const result: Availability[] = []
  for (const avail of availabilitySlices.value) {
    if (hiddenRooms.value.includes(avail.room)) continue
    const start = visibleTimeslices.value.find(slice => slice.date.isSameOrAfter(avail.start))
    const end = visibleTimeslices.value.find(slice => slice.date.isSameOrAfter(avail.end))
    if (!start || !end) continue
    result.push({
      room: avail.room,
      start: start.date,
      end: end.date,
      active: avail.active,
    })
  }
  return result
})

const setTimesliceRef = (el: HTMLElement | null) => {
  if (el && !timesliceRefs.value.includes(el)) timesliceRefs.value.push(el)
}

const startDragging = ({ session, event }: DragEventPayload) => {
  dragStart.value = {
    x: event.clientX,
    y: event.clientY,
    session,
    now: moment(),
  }
  emit('startDragging', { event, session })
}

const stopDragging = (event: PointerEvent) => {
  if (dragStart.value && props.draggedSession) {
    const distance = dragStart.value.x - event.clientX + dragStart.value.y - event.clientY
    const timeDiff = moment().diff(dragStart.value.now, 'ms')
    const session = dragStart.value.session
    dragStart.value = null

    if (Math.abs(distance) < 5 && timeDiff < 500) {
      emit('editSession', session)
      return
    }
  }

  if (!props.draggedSession || !hoverSlice.value || !hoverSliceLegal.value) return
  const start = hoverSlice.value.time
  const end = hoverSlice.value.time.clone().add(props.draggedSession.duration, 'm')

  if (!props.draggedSession.id) {
    // Create a new session object with the correct room format
    const newSessionData: SessionDatum = {
      ...props.draggedSession,
      start: moment(start.format()),
      end: moment(end.format()),
      room: { 
        id: hoverSlice.value.room.id,
        name: hoverSlice.value.room.name
      }
    }
    
    emit('createSession', { session: newSessionData })
  } else {
    emit('rescheduleSession', {
      session: props.draggedSession,
      start: start.format(),
      end: end.format(),
      room: hoverSlice.value.room,
    })
  }
}

const expandTimeslice = (slice: Timeslice) => {
  const index = visibleTimeslices.value.indexOf(slice)
  if (index + 1 >= visibleTimeslices.value.length) {
    expandedTimes.value.push(slice.date.clone().add(5, 'm'))
  } else {
    const end = visibleTimeslices.value[index + 1].date.clone()
    const interval = end.diff(slice.date, 'minutes') <= 30 ? 5 : 30
    const time = slice.date.clone().add(interval, 'm')
    while (time.isBefore(end)) {
      expandedTimes.value.push(time.clone())
      time.add(interval, 'm')
    }
  }
  expandedTimes.value = [...new Set(expandedTimes.value.map(d => d.valueOf()))].map(v => moment(v))
}

const updateHoverSlice = (e: PointerEvent) => {
  if (!props.draggedSession) {
    hoverSlice.value = null
    return
  }

  if (!dragScrollTimer.value) {
    dragScrollTimer.value = setInterval(dragOnScroll, 100)
  }

  let hoverSliceEl: HTMLElement | null = null
  for (const element of document.elementsFromPoint(gridOffset.value, e.clientY)) {
    if (
      element instanceof HTMLElement &&
      element.dataset.slice &&
      element.classList.contains('timeslice')
    ) {
      hoverSliceEl = element
      break
    }
  }

  if (!hoverSliceEl) return
  const roomEls = document.querySelectorAll('.grid .room')
  const roomWidth = roomEls[1]?.getBoundingClientRect().width || 200
  const scrollOffset = scrollParent.value?.scrollLeft || 0
  const roomIndex = Math.floor((e.clientX + scrollOffset - gridOffset.value - 80) / roomWidth)

  hoverSlice.value = {
    time: moment(hoverSliceEl.dataset.slice),
    roomIndex,
    room: visibleRooms.value[roomIndex],
    duration: props.draggedSession.duration,
  }
}

const getHoverSliceStyle = (): Record<string, string> | undefined => {
  if (!hoverSlice.value || !props.draggedSession) return undefined
  return {
    'grid-area': `${getSliceName(hoverSlice.value.time)} / ${hoverSlice.value.roomIndex + 2} / ${getSliceName(
      hoverSlice.value.time.clone().add(hoverSlice.value.duration, 'm')
    )}`,
  }
}

const getSessionStyle = (session: SessionDatum | Availability): Record<string, string | number> => {
  if (!session.room || !session.start) return {}
  const roomIndex = visibleRooms.value.indexOf(session.room)
  return {
    'grid-row': `${getSliceName(session.start)} / ${getSliceName(session.end)}`,
    'grid-column': roomIndex > -1 ? (roomIndex + 2).toString() : '',
  }
}

const getOffsetTop = (): number => staticOffsetTop.value + window.scrollY

const getSliceClasses = (slice: Timeslice): Record<string, boolean> => ({
  datebreak: slice.datebreak || false,
  gap: slice.gap || false,
  expandable: isSliceExpandable(slice),
})

const isSliceExpandable = (slice: Timeslice): boolean => {
  const index = visibleTimeslices.value.indexOf(slice)
  if (index + 1 === visibleTimeslices.value.length) return false
  const nextSlice = visibleTimeslices.value[index + 1]
  return nextSlice.date.diff(slice.date, 'minutes') > 5
}

const getSliceStyle = (slice: Timeslice): Record<string, string> => {
  if (slice.datebreak) {
    let index = timeslices.value.findIndex(s => s.date.isAfter(slice.date, 'day'))
    if (index < 0) index = timeslices.value.length - 1
    return { 'grid-area': `${slice.name} / 1 / ${timeslices.value[index].name} / auto` }
  }
  return { 'grid-area': `${slice.name} / 1 / auto / auto` }
}

const getSliceLabel = (slice: Timeslice): string => {
  if (slice.datebreak) return slice.date.format('ddd[\n]DD. MMM')
  return slice.date.format('LT')
}

const changeDay = (day: Moment | null) => {
  if (!day || scrolledDay.value?.isSame(day)) return

  const el = timesliceRefs.value.find(el => el.dataset?.slice === day.format())
  if (!el) return
  const offset = el.offsetTop + getOffsetTop()
  scrollTo(offset)
  scrolledDay.value = day
  emit('changeDay', day)
}

const scrollTo = (offset: number) => {
  if (scrollParent.value) {
    scrollParent.value.scroll({ top: offset, behavior: 'smooth' })
  }
}

const scrollBy = (offset: number) => {
  if (scrollParent.value) {
    scrollParent.value.scrollBy({ top: offset, behavior: 'smooth' })
  }
}

const dragOnScroll = () => {
  if (!props.draggedSession) {
    if (dragScrollTimer.value) {
      clearInterval(dragScrollTimer.value)
      dragScrollTimer.value = null
    }
    return
  }

  const event = dragStart.value?.session && dragStart.value.session ? dragStart.value.session : null
  if (!dragStart.value) return

  const yPos = dragStart.value.y - staticOffsetTop.value
  const parentHeight = scrollParent.value?.clientHeight ?? 0

  if (yPos < 160) {
    scrollBy(yPos < 90 ? -200 : -75)
  } else if (yPos > parentHeight - 100) {
    scrollBy(yPos > parentHeight - 40 ? 200 : 75)
  }
}

const onIntersect = (entries: IntersectionObserverEntry[]) => {
  // Find the last visible entry by time, which is intersecting
  const entry = entries
    .slice()
    .sort((a, b) => {
      const aDate = (a.target as HTMLElement).dataset.slice
      const bDate = (b.target as HTMLElement).dataset.slice
      return new Date(bDate!).getTime() - new Date(aDate!).getTime()
    })
    .find((e) => e.isIntersecting)
  if (!entry) return
  const day = moment.parseZone((entry.target as HTMLElement).dataset.slice!).startOf('day')
  scrolledDay.value = day
  emit('changeDay', day)
}

watch(() => props.currentDay, (day) => changeDay(day))

onMounted(async () => {
  await nextTick()
  
  if (grid.value) {
    gridOffset.value = grid.value.getBoundingClientRect().left
  }

  observer = new IntersectionObserver(onIntersect, {
    root: scrollParent.value,
    rootMargin: '-45% 0px',
  })

  timesliceRefs.value.forEach(el => {
    if (!el.dataset?.slice || !el.dataset.slice.endsWith('00-00')) return
    observer?.observe(el)
  })
})

onUnmounted(() => {
  timesliceRefs.value = []
  if (observer) {
    observer.disconnect()
    observer = null
  }

  if (dragScrollTimer.value) {
    clearInterval(dragScrollTimer.value)
    dragScrollTimer.value = null
  }
})
</script>

<style lang="stylus">
.c-grid-schedule
	flex: auto
	.grid
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

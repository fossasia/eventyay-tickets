<template lang="pug">
.c-grid-schedule(ref="rootEl", :class="'density-' + density")
	.grid(ref="grid", :style="gridStyle", :class="gridClasses", @click="onGridClick($event)", @pointermove="updateHoverSlice($event)", @pointerup="stopDragging($event)")
		template(v-for="slice of visibleTimeslices", :key="slice.name")
			.timeslice(:ref="setTimesliceRef", :class="getSliceClasses(slice)", :data-slice="slice.date.format()", :style="getSliceStyle(slice)", @click="expandTimeslice(slice)") {{ getSliceLabel(slice) }}
				svg(viewBox="0 0 10 10", v-if="isSliceExpandable(slice)").expand
					path(d="M 0 4 L 5 0 L 10 4 z")
					path(d="M 0 6 L 5 10 L 10 6 z")
			.timeseparator(:class="getSliceClasses(slice)", :style="getSliceStyle(slice)")
		.room(:style="{'grid-area': `1 / 1 / auto / auto`}")
		.room(v-for="(room, i) of visibleRooms", :key="room.id", :style="{'grid-area': `1 / ${i + 2} / auto / auto`}")
			span.room-name(:title="getLocalizedString(room.name)") {{ getLocalizedString(room.name) }}
			.hide-room.no-print(v-if="visibleRooms.length > 1", @click="hiddenRooms = rooms.filter(r => hiddenRooms.includes(r) || r === room)")
				i.fa.fa-eye-slash
		session(v-if="draggedSession && hoverSlice", :style="getHoverSliceStyle()", :session="draggedSession", :isDragClone="true", :overrideStart="hoverSlice.time")
		template(v-for="session of visibleSessions", :key="session.id")
			session(
				v-if="hasValidPosition(session)"
				:session="session",
				:warnings="getSessionWarnings(session)",
				:isDragged="draggedSession && (session.id === draggedSession.id)",
				:style="getSessionStyle(session)",
				:showRoom="false",
				@startDragging="startDragging($event)",
				@editSession="emit('editSession', $event)",
				@deleteSession="emit('deleteSession', $event)",
				@assignMembers="emit('assignMembers', $event)",
			)
		.availability(v-for="availability of visibleAvailabilities", :key="`${availability.room.id}-${availability.start.valueOf()}-${availability.end.valueOf()}`", :style="getSessionStyle(availability)", :class="availability.active ? ['active'] : []")
	#hidden-rooms.no-print(v-if="hiddenRooms.length")
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
import TalkSession from './Session.vue'
import ShiftSession from '~/teamshifts-adapter/Session.vue'
import { resolveMode } from '~/teamshifts-adapter'
import { getLocalizedString } from '~/utils'

const mode = resolveMode()
const Session = mode === 'shifts' || mode === 'public-shifts' ? ShiftSession : TalkSession

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
  density: 'compact' | 'default' | 'comfortable'
  timeDensityMinutes: number
  allowOverlap?: boolean
}>()

const emit = defineEmits([
  'startDragging',
  'editSession',
  'deleteSession',
  'assignMembers',
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
const layoutObservers: ResizeObserver[] = []
let windowResizeListener: (() => void) | null = null
let gridOffsetFrame: number | null = null

const refreshGridOffset = () => {
  if (grid.value) {
    gridOffset.value = grid.value.getBoundingClientRect().left
  }
}

const scheduleRefreshGridOffset = () => {
  if (gridOffsetFrame !== null) {
    return
  }
  gridOffsetFrame = requestAnimationFrame(() => {
    gridOffsetFrame = null
    refreshGridOffset()
  })
}

const observeElementResize = (element: HTMLElement | null) => {
  if (!element || typeof ResizeObserver === 'undefined') {
    return
  }
  const resizeObserver = new ResizeObserver(scheduleRefreshGridOffset)
  resizeObserver.observe(element)
  layoutObservers.push(resizeObserver)
}

const hasValidPosition = (session: SessionDatum): boolean => {
  return !!(session.room && session.start && session.end)
}

const getSliceName = (date: Moment): string => `slice-${date.format('MM-DD-HH-mm')}`

const hoverSliceLegal = computed(() => {
  if (!hoverSlice.value || !hoverSlice.value.room || !props.draggedSession) return false
  if (props.allowOverlap) return true
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
  const minimumSliceMins = props.timeDensityMinutes || 30
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
      const sliceDate = start.clone().add(startingMins + minimumSliceMins * i, 'minutes')
      if (sliceDate.isAfter(end)) break
      halfHourSlices.push(sliceDate)
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
    return slice.date.minutes() % minimumSliceMins !== 0
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
    if (prevSlice && sliceShouldDisplay(prevSlice, index - 1) && !prevSlice.datebreak) {
      prevSlice.gap = true
    }
  }

  return compactedSlices
})

const oddTimeslices = computed<Moment[]>(() => {
  const minimumSliceMins = props.timeDensityMinutes || 30
  const result: Moment[] = []
  props.sessions.forEach(session => {
    if (session.start.minute() % minimumSliceMins !== 0) result.push(session.start)
    if (session.end.minute() % minimumSliceMins !== 0) result.push(session.end)
  })
  // Remove duplicates by stringifying dates (safe as moment objects)
  return [...new Set(result.map(m => m.format()))].map(f => moment(f))
})

const visibleTimeslices = computed<Timeslice[]>(() => {
  const minimumSliceMins = props.timeDensityMinutes || 30
  return timeslices.value.filter(slice =>
    slice.date.minute() % minimumSliceMins === 0 ||
    expandedTimes.value.some(et => et.isSame(slice.date)) ||
    oddTimeslices.value.some(ot => ot.isSame(slice.date))
  )
})

const densityScale = computed(() => {
  if (props.density === 'compact') return 0.65
  if (props.density === 'comfortable') return 1.4
  return 1
})

const gridStyle = computed(() => {
  const scale = densityScale.value
  const minimumSliceMins = props.timeDensityMinutes || 30
  const baseSliceHeight = 60 * (minimumSliceMins / 30)
  let rows = `[header] ${Math.round(52 * scale)}px `
  rows += timeslices.value.map((slice, index) => {
    const next = timeslices.value[index + 1]
    let height = baseSliceHeight
    if (slice.gap) {
      height = 100 * (minimumSliceMins / 30)
    } else if (slice.datebreak) {
      height = baseSliceHeight
    } else if (next) {
      height = Math.min(baseSliceHeight, next.date.diff(slice.date, 'minutes') * 2)
    }
    height = Math.round(height * scale)
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
  refreshGridOffset()
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
    const distance = Math.abs(dragStart.value.x - event.clientX) + Math.abs(dragStart.value.y - event.clientY)
    const timeDiff = moment().diff(dragStart.value.now, 'ms')
    const session = dragStart.value.session
    dragStart.value = null

    if (distance < 6 && timeDiff < 300) {
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
    const minimumSliceMins = props.timeDensityMinutes || 30
    expandedTimes.value.push(slice.date.clone().add(Math.min(5, minimumSliceMins), 'm'))
  } else {
    const end = visibleTimeslices.value[index + 1].date.clone()
    const minimumSliceMins = props.timeDensityMinutes || 30
    const interval = end.diff(slice.date, 'minutes') <= minimumSliceMins ? Math.min(5, minimumSliceMins) : minimumSliceMins
    const time = slice.date.clone().add(interval, 'm')
    while (time.isBefore(end)) {
      expandedTimes.value.push(time.clone())
      time.add(interval, 'm')
    }
  }
  expandedTimes.value = [...new Set(expandedTimes.value.map(d => d.valueOf()))].map(v => moment(v))
}

const getTimeAndRoomFromPoint = (clientX: number, clientY: number) => {
  // 1. Determine room index by checking which room column the pointer is horizontally within
  const roomEls = Array.from(rootEl.value?.querySelectorAll('.grid > .room') || [])
  let roomIndex = -1
  for (let i = 1; i < roomEls.length; i++) {
    const rect = roomEls[i].getBoundingClientRect()
    if (clientX >= rect.left && clientX < rect.right) {
      roomIndex = i - 1
      break
    }
    if (clientX >= rect.right && i === roomEls.length - 1) {
      roomIndex = i - 1
    }
  }
  if (roomIndex < 0 && roomEls.length > 1) {
    if (clientX < roomEls[1].getBoundingClientRect().left) {
      roomIndex = 0
    }
  }
  if (roomIndex < 0 || roomIndex >= visibleRooms.value.length) return null
  const room = visibleRooms.value[roomIndex]

  // 2. Determine timeslice by checking which row the pointer is vertically within
  const timesliceEls = Array.from(rootEl.value?.querySelectorAll('.grid > .timeslice') || []) as HTMLElement[]
  if (!timesliceEls.length) return null

  let targetSliceEl: HTMLElement | null = null
  for (let i = 0; i < timesliceEls.length; i++) {
    const rect = timesliceEls[i].getBoundingClientRect()
    const nextRect = timesliceEls[i + 1]?.getBoundingClientRect()
    const bottom = nextRect ? nextRect.top : rect.bottom
    if (clientY >= rect.top && clientY < bottom) {
      targetSliceEl = timesliceEls[i]
      break
    }
  }
  if (!targetSliceEl) {
    if (clientY < timesliceEls[0].getBoundingClientRect().top) {
      targetSliceEl = timesliceEls[0]
    } else {
      targetSliceEl = timesliceEls[timesliceEls.length - 1]
    }
  }

  if (!targetSliceEl || !targetSliceEl.dataset.slice) return null
  const time = moment(targetSliceEl.dataset.slice)

  return { time, room, roomIndex }
}

let lastPlacementTime = 0

const tryPlaceSessionAtPoint = (clientX: number, clientY: number): boolean => {
  if (!props.draggedSession) return false
  const now = Date.now()
  if (now - lastPlacementTime < 300) return false // prevent duplicate triggers
  lastPlacementTime = now

  const slot = getTimeAndRoomFromPoint(clientX, clientY)
  if (!slot || !slot.room || !slot.time) return false

  const start = slot.time
  const end = slot.time.clone().add(props.draggedSession.duration, 'm')

  if (!props.draggedSession.id) {
    emit('createSession', {
      session: {
        ...props.draggedSession,
        start: moment(start.format()),
        end: moment(end.format()),
        room: {
          id: slot.room.id,
          name: slot.room.name
        }
      }
    })
  } else {
    emit('rescheduleSession', {
      session: props.draggedSession,
      start: start.format(),
      end: end.format(),
      room: slot.room,
    })
  }
  return true
}

const onGridClick = (event: MouseEvent) => {
  if (!props.draggedSession) return
  const target = event.target as HTMLElement
  if (target && target.closest('.c-linear-schedule-session:not(.clone)')) {
    return
  }
  tryPlaceSessionAtPoint(event.clientX, event.clientY)
}

const updateHoverSlice = (e: PointerEvent) => {
  if (!props.draggedSession) {
    hoverSlice.value = null
    return
  }

  if (dragStart.value) {
    dragStart.value = { ...dragStart.value, y: e.clientY }
  }

  if (!dragScrollTimer.value) {
    dragScrollTimer.value = setInterval(dragOnScroll, 100)
  }

  const slot = getTimeAndRoomFromPoint(e.clientX, e.clientY)
  if (!slot) return

  hoverSlice.value = {
    time: slot.time,
    roomIndex: slot.roomIndex,
    room: slot.room,
    duration: props.draggedSession.duration,
  }
}

// Document-level handler: catches touch pointermove even when captured by a session element
const onDocPointerMove = (e: PointerEvent) => {
  if (props.draggedSession && e.isPrimary) {
    updateHoverSlice(e)
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

const getSessionWarnings = (session: SessionDatum): { message: string }[] => {
  return session.code ? (props.warnings[session.code] || []) : []
}

const getOverlapGroup = (session: SessionDatum | Availability): { index: number; total: number } => {
  if (!session.room || !session.start || !session.end) return { index: 0, total: 1 }
  if (!('id' in session)) return { index: 0, total: 1 }

  const overlapping = visibleSessions.value.filter(s => {
    if (s.id === (session as SessionDatum).id) return true
    if (!s.room || !s.start || !s.end) return false
    if (s.room.id !== session.room.id) return false
    return s.start.isBefore(session.end) && s.end.isAfter(session.start)
  })

  return { index: 0, total: overlapping.length }
}

const getSessionStyle = (session: SessionDatum | Availability): Record<string, string | number> => {
  if (!session.room || !session.start) return {}
  const roomIndex = visibleRooms.value.indexOf(session.room)
  const { total } = getOverlapGroup(session)

  if (props.allowOverlap && total > 1 && 'id' in session) {
    const overlapping = visibleSessions.value.filter(s => {
      if (!s.room || !s.start || !s.end) return false
      if (s.room.id !== session.room!.id) return false
      return s.start.isBefore(session.end) && s.end.isAfter(session.start)
    }).sort((a, b) => {
      const diff = a.start.diff(b.start)
      return diff !== 0 ? diff : a.id - b.id
    })
    const myIndex = overlapping.findIndex(s => s.id === (session as SessionDatum).id)
    if (myIndex === 0) {
      return {
        'grid-row-start': getSliceName(session.start),
        'grid-column': roomIndex > -1 ? (roomIndex + 2).toString() : '',
      }
    }
    const prev = overlapping[myIndex - 1]
    return {
      'grid-row-start': getSliceName(prev.end),
      'grid-column': roomIndex > -1 ? (roomIndex + 2).toString() : '',
    }
  }

  return {
    'grid-row': `${getSliceName(session.start)} / ${getSliceName(session.end)}`,
    'grid-column': roomIndex > -1 ? (roomIndex + 2).toString() : '',
  }
}


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
  const roomEl = rootEl.value?.querySelector('.room')
  const controlsEl = rootEl.value?.parentElement?.querySelector('.schedule-controls')
  const headerHeight = (roomEl?.getBoundingClientRect().height || 52) + (controlsEl?.getBoundingClientRect().height || 48)
  const offset = Math.max(0, el.offsetTop - headerHeight)
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

  refreshGridOffset()
  observeElementResize(rootEl.value)
  const layoutRoot = rootEl.value?.closest('#page-content') ?? rootEl.value?.closest('.pretalx-schedule')
  if (layoutRoot instanceof HTMLElement && layoutRoot !== rootEl.value) {
    observeElementResize(layoutRoot)
  }
  if (typeof ResizeObserver === 'undefined') {
    windowResizeListener = scheduleRefreshGridOffset
    window.addEventListener('resize', windowResizeListener)
  }

  // Listen on document level so touch drags (where pointer is captured elsewhere) work
  document.addEventListener('pointermove', onDocPointerMove)

  observer = new IntersectionObserver(onIntersect, {
    root: scrollParent.value,
    rootMargin: '-45% 0px',
  })

  timesliceRefs.value.forEach(el => {
    if (!el.dataset?.slice || !el.classList.contains('datebreak')) return
    observer?.observe(el)
  })
})

onUnmounted(() => {
  timesliceRefs.value = []
  document.removeEventListener('pointermove', onDocPointerMove)
  if (gridOffsetFrame !== null) {
    cancelAnimationFrame(gridOffsetFrame)
    gridOffsetFrame = null
  }
  layoutObservers.forEach((resizeObserver) => resizeObserver.disconnect())
  layoutObservers.length = 0
  if (windowResizeListener) {
    window.removeEventListener('resize', windowResizeListener)
    windowResizeListener = null
  }
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
		@media (max-width: 767px)
			grid-template-columns: 78px repeat(var(--total-rooms), minmax(260px, 1fr)) auto
		position: relative
		min-width: min-content
		&.illegal-hover
			cursor: not-allowed
			.c-linear-schedule-session
				cursor: not-allowed
		> .room
			position: sticky
			top: calc(48px)
			display: flex
			justify-content: center
			align-items: center
			font-size: 18px
			background-color: $clr-white
			border-bottom: 1px solid $clr-dividers-light
			z-index: 40
			min-width: 0
			box-sizing: border-box
			padding: 8px 12px
			&:first-child
				left: 0
				top: calc(48px)
				z-index: 45
				min-width: 78px
				width: 78px
				padding: 0
				background-color: $clr-white

			.room-name
				overflow: hidden
				text-overflow: ellipsis
				white-space: nowrap
				min-width: 0
				padding: 0 4px

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
			transition: padding 0.2s ease, font-size 0.2s ease
	.timeslice
		color: $clr-secondary-text-light
		padding: 8px 10px 0 10px
		white-space: nowrap
		position: sticky
		left: 0
		width: 78px
		min-width: 78px
		box-sizing: border-box
		text-align: center
		background-color: $clr-grey-50
		border-top: 1px solid $clr-dividers-light
		z-index: 25
		transition: padding 0.2s ease, font-size 0.2s ease
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

	// Density: compact
	&.density-compact
		.timeslice
			padding: 4px 6px 0 6px
			font-size: 12px
		.grid-viewport .grid
			.c-linear-schedule-session, .break
				margin: 4px 3px
				min-height: 48px
				font-size: 12px
		.c-linear-schedule-session
			min-height: 48px
			font-size: 12px
			.time-box
				width: 50px
				padding: 4px 4px 2px 4px
				.start
					font-size: 13px
					margin-bottom: 4px
					.duration
						font-size: 11px
			.info
				padding: 4px 6px
				.title
					font-size: 13px
					margin-bottom: 2px
				.speakers
					font-size: 11px
		.grid > .room
			font-size: 14px
			padding: 4px

	// Density: comfortable
	&.density-comfortable
		.timeslice
			padding: 12px 14px 0 14px
			font-size: 15px
		.grid-viewport .grid
			.c-linear-schedule-session, .break
				margin: 12px 9px
				min-height: 120px
				font-size: 15px
		.c-linear-schedule-session
			min-height: 120px
			font-size: 15px
			.time-box
				width: 72px
				padding: 14px 10px 8px 10px
				.start
					font-size: 18px
					margin-bottom: 10px
					.duration
						font-size: 14px
			.info
				padding: 12px
				.title
					font-size: 18px
					margin-bottom: 6px
				.speakers
					font-size: 14px
		.grid > .room
			font-size: 20px
			padding: 12px

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
#hidden-rooms
	position: fixed
	z-index: 500
	bottom: 0
	right: 0
	width: 300px
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
		border-bottom: 1px solid $clr-dividers-light
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

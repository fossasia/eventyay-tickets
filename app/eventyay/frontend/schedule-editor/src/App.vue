<template lang="pug">
.pretalx-schedule(:style="{'--scrollparent-width': scrollParentWidth + 'px'}", :class="draggedSession ? ['is-dragging'] : []", @pointerup="stopDragging")
	template(v-if="schedule")
		#main-wrapper
			#unassigned.no-print(v-scrollbar.y="", @pointerenter="isUnassigning = true", @pointerleave="isUnassigning = false")
				.title
					bunt-input#filter-input(v-model="unassignedFilterString", :placeholder="translations.filterSessions", icon="search", name="filter-input")
					#unassigned-sort(@click="showUnassignedSortMenu = !showUnassignedSortMenu", :class="{'active': showUnassignedSortMenu}")
						i.fa.fa-sort
					#unassigned-sort-menu(v-if="showUnassignedSortMenu")
						.sort-method(v-for="method of unassignedSortMethods", @click="unassignedSort === method.name ? unassignedSortDirection = unassignedSortDirection * -1 : unassignedSort = method.name; showUnassignedSortMenu = false")
							span {{ method.label }}
							i.fa.fa-sort-amount-asc(v-if="unassignedSort === method.name && unassignedSortDirection === 1")
							i.fa.fa-sort-amount-desc(v-if="unassignedSort === method.name && unassignedSortDirection === -1")
				session.new-break(:session="{title: '+ ' + translations.newBreak}", :isDragged="false", @startDragging="startNewBreak", @click="showNewBreakHint", v-tooltip.fixed="{text: newBreakTooltip, show: newBreakTooltip}", @pointerleave="removeNewBreakHint")
				session(v-for="un in unscheduled", :key="un.id", :session="un", @startDragging="startDragging", :isDragged="draggedSession && un.id === draggedSession.id")
			#schedule-wrapper(v-scrollbar.x.y="")
				bunt-tabs.days(v-if="days", :modelValue="currentDay.format()", ref="tabs" :class="['grid-tabs']")
					bunt-tab(v-for="day of days", :key="day.format()", :id="day.format()", :header="day.format(dateFormat)", @selected="changeDay(day)")
				grid-schedule(:sessions="sessions",
					:rooms="schedule.rooms",
					:availabilities="availabilities",
					:warnings="warnings",
					:start="days[0]",
					:end="days.at(-1).clone().endOf('day')",
					:currentDay="currentDay",
					:draggedSession="draggedSession",
					@changeDay="currentDay = $event",
					@startDragging="startDragging",
					@rescheduleSession="rescheduleSession",
					@createSession="createSession",
					@editSession="editorStart($event)")
			#session-editor-wrapper(v-if="editorSession", @click="editorSession = null")
				form#session-editor(@click.stop="", @submit.prevent="editorSave")
					h3.session-editor-title(v-if="editorSession.code")
						a(v-if="editorSession.code", :href="`/orga/event/${eventSlug}/submissions/${editorSession.code}/`") {{ getLocalizedString(editorSession.title) }}
						span(v-else) {{ getLocalizedString(editorSession.title) }}
					.data
						.data-row(v-if="editorSession.code && editorSession.speakers && editorSession.speakers.length > 0").form-group.row
							label.data-label.col-form-label.col-md-3 {{ $t('Speakers') }}
							.col-md-9.data-value
								span(v-for="speaker, index of editorSession.speakers")
									a(:href="`/orga/event/${eventSlug}/speakers/${speaker.code}/`") {{speaker.name || speaker.code}}
									span(v-if="index != editorSession.speakers.length - 1") {{', '}}
								span.text-warning(v-if="editorSession.speakers.some(s => !s.name)")  ({{ $t('names not shared by speaker') }})
						.data-row(v-else).form-group.row
							label.data-label.col-form-label.col-md-3 {{ $t('Title') }}
							.col-md-9
								.i18n-form-group
									template(v-for="locale of locales")
										input(v-model="editorSession.title[locale]", :required="true", :lang="locale", type="text")
						.data-row(v-if="editorSession.track").form-group.row
							label.data-label.col-form-label.col-md-3 {{ $t('Track') }}
							.col-md-9.data-value {{ getLocalizedString(editorSession.track.name) }}
						.data-row(v-if="editorSession.room").form-group.row
							label.data-label.col-form-label.col-md-3 {{ $t('Room') }}
							.col-md-9.data-value {{ getLocalizedString(editorSession.room.name) }}
						.data-row.form-control.form-group.row
							label.data-label.col-form-label.col-md-3 {{ $t('Duration') }}
							.col-md-9.number.input-group
								input(v-model="editorSession.duration", type="number", min="1", max="1440", step="1", :required="true")
								.input-group-append
									span.input-group-text {{ $t('minutes') }}

						.data-row(v-if="editorSession.code && warnings[editorSession.code] && warnings[editorSession.code].length").form-group.row
							label.data-label.col-form-label.col-md-3
								i.fa.fa-exclamation-triangle.warning
								span {{ $t('Warnings') }}
							.col-md-9.data-value
								ul(v-if="warnings[editorSession.code].length > 1")
									li.warning(v-for="warning of warnings[editorSession.code]") {{ warning.message }}
								span(v-else) {{ warnings[editorSession.code][0].message }}
					.button-row
						input(type="submit")
						bunt-button#btn-delete(v-if="!editorSession.code", @click="editorDelete", :loading="editorSessionWaiting") {{ $t('Delete') }}
						bunt-button#btn-save(@click="editorSave", :loading="editorSessionWaiting") {{ $t('Save') }}
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>

<script lang="ts" setup>
import { ref, reactive, computed, onMounted, onUnmounted, onBeforeMount, nextTick } from 'vue'
import moment, { Moment } from 'moment-timezone'
import GridSchedule from '~/components/GridSchedule.vue'
import Session from '~/components/Session.vue'
import api from '~/api'
import { getLocalizedString } from '~/utils'
import type { AvailabilityEntry } from '~/schemas';

interface Speaker {
  code: string
  name: string
}

interface Track {
  id: string
  name: Record<string, string> // localized names
}

interface Room {
  id: string
  name: Record<string, string>
}

interface Warning {
  message: string
}

interface Talk {
  id: number
  code: string
  title: Record<string, string>
  abstract?: string
  speakers?: string[] // array of speaker codes
  track?: string
  room?: string
  duration: number
  start?: string | null
  end?: string | null
  state?: string
  updated?: string
  submission?: Record<string, unknown>
  uncreated?: boolean
  availabilities?: AvailabilityEntry[]
}

interface SessionData {
  id: number
  code: string
  title: Record<string, string> | string
  abstract?: string
  speakers?: Speaker[]
  track?: Track
  duration?: number
  start?: Moment
  end?: Moment
  state?: string
  room?: Room
  uncreated?: boolean
  availabilities?: AvailabilityEntry[]
}

interface SortMethod {
  label: string
  name: string
}

interface Schedule {
  version: string
  event_start: string
  event_end: string
  timezone: string
  locales: string[]
  rooms: Room[]
  tracks: Track[]
  speakers: Speaker[]
  talks: Talk[]
  now?: string
}

const props = defineProps<{
  locale: string
}>()

const eventSlug = ref<string | null>(null)
const scrollParentWidth = ref<number>(Infinity)
const schedule = ref<Schedule | null>(null)
const availabilities = reactive<{ rooms: Record<string, AvailabilityEntry[]>; talks: Record<string, AvailabilityEntry[]> }>({
  rooms: {},
  talks: {},
})
const warnings = reactive<Record<string, Warning[]>>({})
const currentDay = ref<Moment | null>(null)
const draggedSession = ref<SessionData | null>(null)
const editorSession = ref<SessionData | null>(null)
const editorSessionWaiting = ref<boolean>(false)
const isUnassigning = ref<boolean>(false)
const locales = ref<string[]>(['en'])
const unassignedFilterString = ref<string>('')
const unassignedSort = ref<string>('title')
const unassignedSortDirection = ref<number>(1)
const showUnassignedSortMenu = ref<boolean>(false)
const newBreakTooltip = ref<string>('')
const eventTimezone = ref<string | null>(null)
const since = ref<string | undefined>(undefined)

function $t(key: string): string {
  return typeof window !== 'undefined' && (window as { $t?: (key: string) => string }).$t?.(key) || key;
}

const translations = reactive({
  filterSessions: $t('Filter sessions'),
  newBreak: $t('New break'),
})

// Lookups
const roomsLookup = computed<Record<string, Room>>(() => {
  if (!schedule.value) return {}
  return schedule.value.rooms.reduce((acc, room) => {
    acc[room.id] = room
    return acc
  }, {} as Record<string, Room>)
})

const tracksLookup = computed<Record<string, Track>>(() => {
  if (!schedule.value) return {}
  return schedule.value.tracks.reduce((acc, track) => {
    acc[track.id] = track
    return acc
  }, {} as Record<string, Track>)
})

const speakersLookup = computed<Record<string, Speaker>>(() => {
  if (!schedule.value) return {}
  return schedule.value.speakers.reduce((acc, speaker) => {
    acc[speaker.code] = speaker
    return acc
  }, {} as Record<string, Speaker>)
})

// Sort methods for unassigned sessions
const unassignedSortMethods = computed<SortMethod[]>(() => {
  const sortMethods: SortMethod[] = [
    { label: $t('Title'), name: 'title' },
    { label: $t('Speakers'), name: 'speakers' },
  ]
  if (schedule.value && schedule.value.tracks.length > 1) {
    sortMethods.push({ label: $t('Track'), name: 'track' })
  }
  sortMethods.push({ label: $t('Duration'), name: 'duration' })
  return sortMethods
})

// Sessions without start or room (unassigned)
const unscheduled = computed<SessionData[]>(() => {
  if (!schedule.value) return []
  let sessions: SessionData[] = []
  for (const session of schedule.value.talks.filter((s) => !s.start || !s.room)) {
    sessions.push({
      id: session.id,
      code: session.code,
      title: session.title,
      abstract: session.abstract,
      speakers: session.speakers?.map((s) => speakersLookup.value[s]) ?? [],
      track: tracksLookup.value[session.track ?? ''],
      duration: session.duration,
      state: session.state,
    } as SessionData)
  }
  if (unassignedFilterString.value.length) {
    sessions = sessions.filter((s) => {
      const title = typeof s.title === 'string' ? s.title : getLocalizedString(s.title)
      const speakers = s.speakers?.map((sp) => sp.name).join(', ') || ''
      const filterLower = unassignedFilterString.value.toLowerCase()
      return title.toLowerCase().includes(filterLower) || speakers.toLowerCase().includes(filterLower)
    })
  }
  sessions = sessions.sort((a, b) => {
    if (unassignedSort.value == 'title') {
      return (
        getLocalizedString(typeof a.title === 'string' ? { en: a.title } : a.title)
          .toUpperCase()
          .localeCompare(
            getLocalizedString(typeof b.title === 'string' ? { en: b.title } : b.title).toUpperCase(),
          ) * unassignedSortDirection.value
      )
    } else if (unassignedSort.value == 'speakers') {
      const aSpeakers = a.speakers?.map((s) => s.name).join(', ') || ''
      const bSpeakers = b.speakers?.map((s) => s.name).join(', ') || ''
      return aSpeakers.toUpperCase().localeCompare(bSpeakers.toUpperCase()) * unassignedSortDirection.value
    } else if (unassignedSort.value == 'track') {
      const aTrack = a.track ? getLocalizedString(a.track.name) : ''
      const bTrack = b.track ? getLocalizedString(b.track.name) : ''
      return aTrack.toUpperCase().localeCompare(bTrack.toUpperCase()) * unassignedSortDirection.value
    } else if (unassignedSort.value == 'duration') {
      return ((a.duration ?? 0) - (b.duration ?? 0)) * unassignedSortDirection.value
    }
    return 0
  })
  return sessions
})

const sessions = computed<SessionData[]>(() => {
  if (!schedule.value) return []
  const dayStart = days.value[0]
  const dayEnd = days.value.at(-1)?.clone().endOf('day')
  if (!dayStart || !dayEnd) return []

  const filteredSessions = schedule.value.talks.filter(
    (s) =>
      s.start &&
      moment(s.start).isSameOrAfter(dayStart) &&
      moment(s.start).isSameOrBefore(dayEnd),
  )

  const sessionList: SessionData[] = filteredSessions.map((session) => ({
    id: session.id,
    code: session.code,
    title: session.title,
    abstract: session.abstract,
    start: moment(session.start),
    end: moment(session.end),
    duration: moment(session.end).diff(moment(session.start), 'minutes'),
    speakers: session.speakers?.map((s) => speakersLookup.value[s]) ?? [],
    track: tracksLookup.value[session.track ?? ''],
    state: session.state,
    room: roomsLookup.value[session.room ?? ''],
  }))

  sessionList.sort((a, b) => a.start!.diff(b.start!))
  return sessionList
})

const days = computed<Moment[]>(() => {
  if (!schedule.value) return []
  const daysArray: Moment[] = [moment(schedule.value.event_start).startOf('day')]
  const lastDay = moment(schedule.value.event_end)
  while (!daysArray.at(-1)!.isSame(lastDay, 'day')) {
    daysArray.push(daysArray.at(-1)!.clone().add(1, 'days'))
  }
  return daysArray
})

const dateFormat = computed<string>(() => {
  if (
    (schedule.value && schedule.value.rooms.length > 2) ||
    !days.value ||
    !days.value.length
  )
    return 'dddd DD. MMMM'
  if (days.value && days.value.length <= 5) return 'dddd DD. MMMM'
  if (days.value && days.value.length <= 7) return 'dddd DD. MMM'
  return 'ddd DD. MMM'
})

async function fetchSchedule(options?: Record<string, any>): Promise<Schedule> {
  const sched = await api.fetchTalks(options) as unknown as Schedule
  return sched
}

async function fetchAdditionalScheduleData(): Promise<void> {
  Object.assign(availabilities, await api.fetchAvailabilities() as unknown)
  Object.assign(warnings, await api.fetchWarnings() as unknown)
}

function changeDay(day: Moment): void {
  if (day.isSame(currentDay.value)) return
  currentDay.value = day.clone().tz(eventTimezone.value ?? 'UTC').startOf('day')
  window.location.hash = day.format('YYYY-MM-DD')
}

function saveTalk(session: Talk): void {
  api.saveTalk(session as any).then((response: any) => {
    if (response) {
      warnings[session.code] = response.warnings
      const talk = schedule.value?.talks.find((s) => s.id === session.id)
      if (talk) talk.updated = response.updated
    }
  })
}

interface RescheduleEvent {
  session: SessionData
  start: string | Moment
  end: string | Moment
  room: Room
}

function rescheduleSession(e: RescheduleEvent): void {
  if (!schedule.value) return
  const movedSession = schedule.value.talks.find((s) => s.id === e.session.id)
  stopDragging()
  if (!movedSession) return
  movedSession.start = e.start as string
  movedSession.end = e.end as string
  movedSession.room = e.room.id
  saveTalk(movedSession)
}

interface CreateSessionEvent {
  session: Talk
}

async function createSession(e: CreateSessionEvent): Promise<void> {
  const response: any = await api.createTalk(e.session as any)
  warnings[e.session.code] = response.warnings
  const newSession = { ...e.session, id: response.id }
  if (schedule.value) {
    schedule.value.talks = [...schedule.value.talks, newSession]
  }
  
  editorStart(newSession)
}

function editorStart(session: SessionData | Talk): void {
  editorSession.value = { ...session } as SessionData
}

function editorSave(): void {
  if (!editorSession.value) return

  editorSessionWaiting.value = true
  if (editorSession.value.start) {
    const startMoment = moment(editorSession.value.start)
    editorSession.value.end = startMoment.clone().add(editorSession.value.duration ?? 0, 'minutes')
  }
  
  const talk: Talk = {
    id: editorSession.value.id,
    code: editorSession.value.code,
    title: typeof editorSession.value.title === 'string' 
      ? { en: editorSession.value.title } 
      : editorSession.value.title,
    duration: editorSession.value.duration ?? 0,
    start: editorSession.value.start?.toISOString(),
    end: editorSession.value.end?.toISOString(),
    room: editorSession.value.room?.id,
    speakers: editorSession.value.speakers?.map(s => s.code),
    track: editorSession.value.track?.id,
    abstract: editorSession.value.abstract,
    state: editorSession.value.state
  }
  
  saveTalk(talk)

  const sessionInSchedule = schedule.value?.talks.find((s) => s.id === editorSession.value?.id)
  if (sessionInSchedule && editorSession.value) {
    sessionInSchedule.end = editorSession.value.end?.toISOString()
    if (!('submission' in sessionInSchedule)) {
      sessionInSchedule.title = editorSession.value.title as Record<string, string>
    }
  }
  editorSessionWaiting.value = false
  editorSession.value = null
}

function editorDelete() {
  if (!editorSession.value) return
  editorSessionWaiting.value = true
  api.deleteTalk({ id: String(editorSession.value.id) } as any)
  if (schedule.value) {
    schedule.value.talks = schedule.value.talks.filter((s) => s.id !== editorSession.value?.id)
  }
  editorSessionWaiting.value = false
  editorSession.value = null
}

function showNewBreakHint() {
  newBreakTooltip.value = $t('Drag the box to the schedule to create a new break')
}

function removeNewBreakHint() {
  newBreakTooltip.value = ''
}

interface DragStartEvent {
  event: PointerEvent
  session: Partial<SessionData & Talk>
}

function startNewBreak({ event }: DragStartEvent) {
  const title = locales.value.reduce((obj: Record<string, string>, locale) => {
    obj[locale] = $t('New break')
    return obj
  }, {})
  startDragging({ event, session: { title, duration: 5, uncreated: true } })
}

function startDragging({ event, session }: DragStartEvent) {
  if (availabilities && availabilities.talks[session.id! ?? 0] && availabilities.talks[session.id! ?? 0].length !== 0) {
    session.availabilities = availabilities.talks[session.id! ?? 0]
  }
  draggedSession.value = session as SessionData
}

function stopDragging() {
  try {
    if (isUnassigning.value && draggedSession.value) {
      if (draggedSession.value.code) {
        const movedSession = schedule.value?.talks.find((s) => s.id === draggedSession.value!.id)
        if (movedSession) {
          movedSession.start = null
          movedSession.end = null
          movedSession.room = undefined
          saveTalk(movedSession)
        }
      } else if (schedule.value?.talks.find((s) => s.id === draggedSession.value!.id)) {
        schedule.value.talks = schedule.value.talks.filter((s) => s.id !== draggedSession.value!.id)
        api.deleteTalk({ id: String(draggedSession.value.id) } as any)
      }
    }
  } finally {
    draggedSession.value = null
    isUnassigning.value = false
  }
}

function onWindowResize() {
  scrollParentWidth.value = document.body.offsetWidth
}

async function pollUpdates() {
  if (!schedule.value) return
  const sched = await fetchSchedule({ since: since.value, warnings: true })
  if (sched.version !== schedule.value.version) {
    window.location.reload()
    return
  }
  const updatedTalks = [...schedule.value.talks]
  let hasUpdates = false
  sched.talks.forEach((talk) => {
    const oldTalk = updatedTalks.find((t) => t.id === talk.id)
    if (!oldTalk) {
      updatedTalks.push(talk)
      hasUpdates = true
    } else if (moment(talk.updated).isAfter(moment(oldTalk.updated))) {
      Object.assign(oldTalk, talk)
      hasUpdates = true
    }
  })
  if (hasUpdates) {
    schedule.value.talks = updatedTalks
  }
  since.value = sched.now || schedule.value.now
  window.setTimeout(pollUpdates, 10 * 125)
}

onBeforeMount(async () => {
  schedule.value = await fetchSchedule()
  eventTimezone.value = schedule.value.timezone
  moment.tz.setDefault(eventTimezone.value)
  locales.value = schedule.value.locales
  eventSlug.value = window.location.pathname.split('/')[3] ?? null
  currentDay.value = days.value[0]
  window.setTimeout(pollUpdates, 10 * 100)
  await fetchAdditionalScheduleData()
  await new Promise<void>((resolve) => {
    const poll = () => {
      const el = document.querySelector('.pretalx-schedule')
      // @ts-ignore
      if (el && (el.parentElement || el.getRootNode().host)) return resolve()
      setTimeout(poll, 100)
    }
    poll()
  })
})

onMounted(() => {
  window.addEventListener('resize', onWindowResize)
  onWindowResize()
})

onUnmounted(() => {
  window.removeEventListener('resize', onWindowResize)
})
</script>

<style lang="stylus">
#page-content
	padding: 0
.pretalx-schedule
	display: flex
	flex-direction: column
	min-height: 0
	min-width: 0
	height: calc(100vh - 160px)
	width: 100%
	font-size: 14px
	margin-left: 24px
	font-family: var(--font-family)
	color: var(--color-text)
	h1, h2, h3, h4, h5, h6, legend, button, .btn
		font-family: var(--font-family-title)
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
		tabs-style(active-color: var(--color-primary), indicator-color: var(--color-primary), background-color: transparent)
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
		margin-top: 35px
		width: 350px
		flex: none
		> *
			margin-right: 12px
		> .bunt-scrollbar-rail-y
			margin: 0
		> .title
			padding 4px 0
			font-size: 18px
			text-align: center
			background-color: $clr-white
			border-bottom: 4px solid $clr-dividers-light
			display: flex
			align-items: flex-end
			margin-left: 8px
			#filter-input
				width: calc(100% - 36px)
				.label-input-container, .label-input-container:active
					.outline
						display: none
			#unassigned-sort
				width: 28px
				height: 28px
				text-align: center
				cursor: pointer
				border-radius: 4px
				margin-bottom: 8px
				margin-left: 4px
				color: $clr-secondary-text-light
				&:hover, &.active
					opacity: 0.8
					background-color: $clr-dividers-light
		.new-break.c-linear-schedule-session
			min-height: 48px
		#unassigned-sort-menu
			color: $clr-primary-text-light
			display: flex
			flex-direction: column
			background-color: white
			position: absolute
			top: 53px
			right: 15px
			width: 130px
			font-size: 16px
			cursor: pointer
			z-index: 1000
			box-shadow: 0 2px 4px rgba(0, 0, 0, 0.5)
			text-align: left;
			.sort-method
				padding: 8px 16px
				display: flex
				justify-content: space-between
				align-items: center
				&:hover
					background-color: $clr-dividers-light
	#schedule-wrapper
		width: 100%
		margin-right: 40px
  #session-editor-wrapper
		position: absolute
		z-index: 1000
		top: 0
		left: 0
		width: 100%
		height: 100%
		background-color: rgba(0, 0, 0, 0.5)

		#session-editor
			background-color: $clr-white
			border-radius: 4px
			padding: 32px 40px
			position: absolute
			top: 50%
			left: 50%
			transform: translate(-50%, -50%)
			width: 680px

			.session-editor-title
				font-size: 22px
				margin-bottom: 16px
			.button-row
				display: flex
				width: 100%
				margin-top: 24px

				.bunt-button-content
					font-size: 16px !important
				#btn-delete
					button-style(color: $clr-danger, text-color: $clr-white)
					font-weight: bold;
				#btn-save
					margin-left: auto
					font-weight: bold;
					button-style(color: #2185d0)
				[type=submit]
					display: none
			.data
				display: flex
				flex-direction: column
				font-size: 16px
				.data-row
					.data-value
						padding-top: 8px
						ul
							list-style: none
							padding: 0
			.warning
				color: #b23e65
</style>

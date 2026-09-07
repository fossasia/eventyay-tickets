<template lang="pug">
.pretalx-schedule(:style="{'--scrollparent-width': scrollParentWidth + 'px'}", :class="[draggedSession ? 'is-dragging' : '', !caps.canDrag ? 'is-public-shifts' : '']", @pointerup="caps.canDrag ? stopDragging() : null")
	template(v-if="schedule")
		#main-wrapper
			#unassigned.no-print(v-if="caps.canDrag", v-scrollbar.y="", :class="{'is-collapsed': isUnassignedCollapsed}", @pointerenter="isUnassigning = true", @pointerleave="onUnassignedLeave")
				.unassigned-mobile-header(@click="isUnassignedCollapsed = !isUnassignedCollapsed")
					span.unassigned-title
						i.fa.fa-list
						span {{ $t('Unassigned Sessions') }} ({{ unscheduled.length }})
						span.drop-hint(v-if="draggedSession")  - {{ $t('Drop here to unassign') }}
					span.unassigned-collapse-icon
						i.fa(:class="isUnassignedCollapsed ? 'fa-chevron-down' : 'fa-chevron-up'")
				.unassigned-body
					.unassigned-header
						.density-controls
							button.density-btn(:class="{active: condensedView}", @click="toggleCondensedView", :title="condensedView ? $t('Normal view') : $t('Condensed view')", :aria-pressed="condensedView.toString()")
								i.fa(:class="condensedView ? 'fa-expand' : 'fa-compress'", aria-hidden="true")
								span.density-btn-text {{ condensedView ? $t('Normal view') : $t('Condensed view') }}
							.select-wrapper.custom-dropdown(ref="customDropdownRef", @click="showTimeDensityMenu = !showTimeDensityMenu", :class="{'active': showTimeDensityMenu}")
								span.time-density-display {{ timeDensityMinutes }} {{ $t('min') }}
								i.fa.fa-chevron-down(aria-hidden="true")
								.time-density-menu.vue-dropdown(v-if="showTimeDensityMenu")
									.density-option(v-for="mins in [5, 15, 30, 60]", @click.stop="timeDensityMinutes = mins; onTimeDensityChange(); showTimeDensityMenu = false", :class="{active: timeDensityMinutes === mins}")
							session.new-break.small-break(v-if="caps.canCreateBreak", :session="{title: '+ ' + translations.newBreak}", :isDragged="false", tabindex="0", @startDragging="startNewBreak", @click.stop="showNewBreakHint", @focus="showNewBreakHint", @blur="removeNewBreakHint", @keydown="onNewBreakKeydown", @pointerleave="removeNewBreakHint", :aria-describedby="newBreakTooltip ? 'new-break-hint' : undefined")
							.new-break-hint(v-if="newBreakTooltip", id="new-break-hint", role="tooltip") {{ newBreakTooltip }}
						.title
							bunt-input#filter-input(v-model="unassignedFilterString", :placeholder="translations.filterSessions", icon="search", name="filter-input")
							#unassigned-sort(@click="showUnassignedSortMenu = !showUnassignedSortMenu", :class="{'active': showUnassignedSortMenu}")
								i.fa.fa-sort
							#unassigned-sort-menu(v-if="showUnassignedSortMenu")
								.sort-method(v-for="method of unassignedSortMethods", @click="unassignedSort === method.name ? unassignedSortDirection = unassignedSortDirection * -1 : unassignedSort = method.name; showUnassignedSortMenu = false")
									span {{ method.label }}
									i.fa.fa-sort-amount-asc(v-if="unassignedSort === method.name && unassignedSortDirection === 1")
									i.fa.fa-sort-amount-desc(v-if="unassignedSort === method.name && unassignedSortDirection === -1")
						session.new-break.desktop-break(v-if="caps.canCreateBreak", :session="{title: '+ ' + translations.newBreak}", :isDragged="false", tabindex="0", @startDragging="startNewBreak", @click.stop="showNewBreakHint", @focus="showNewBreakHint", @blur="removeNewBreakHint", @keydown="onNewBreakKeydown", @pointerleave="removeNewBreakHint", :aria-describedby="newBreakTooltip ? 'new-break-hint' : undefined")
						.new-break-hint(v-if="newBreakTooltip", id="new-break-hint", role="tooltip") {{ newBreakTooltip }}
					session(v-for="un in unscheduled", :key="un.id", :session="un", @startDragging="startDragging", :isDragged="draggedSession && un.id === draggedSession.id", @editSession="editorStart($event)", @deleteSession="deleteSessionDirect($event)", @assignMembers="openAssignModal($event)")
					.deleted-room-sessions(v-if="deletedRoomSessions.length")
						h3 {{ caps.showRoles ? $t('Deleted Room Shifts') : $t('Deleted Room Sessions') }}
						p {{ caps.showRoles ? $t('These shifts were assigned to a room that has been deleted. Drag them into another room to restore them to the schedule.') : $t('These sessions were assigned to a room that has been deleted. Drag them into another room to restore them to the schedule.') }}
						session(v-for="session in deletedRoomSessions", :key="session.id", :session="session", @startDragging="startDragging", :isDragged="draggedSession && session.id === draggedSession.id")
			#schedule-wrapper(v-scrollbar.x.y="")
				.schedule-controls
					bunt-tabs.days(v-if="days", :modelValue="currentDay.format()", ref="tabs" :class="['grid-tabs']")
						bunt-tab(v-for="day of days", :key="day.format()", :id="day.format()", :header="day.format(dateFormat)", @selected="changeDay(day)")
				grid-schedule(:sessions="sessions",
					:density="gridDensity",
					:timeDensityMinutes="timeDensityMinutes",
					:rooms="schedule.rooms",
					:availabilities="availabilities",
					:warnings="warnings",
					:start="days[0]",
					:end="days.at(-1).clone().endOf('day')",
					:currentDay="currentDay",
					:draggedSession="draggedSession",
					:allowOverlap="caps.allowOverlap",
					@changeDay="changeDay",
					@startDragging="caps.canDrag ? startDragging($event) : null",
					@rescheduleSession="caps.canDrag ? rescheduleSession($event) : null",
					@createSession="caps.canEdit ? createSession($event) : null",
					@editSession="caps.canEdit ? editorStart($event) : null",
					@deleteSession="caps.canDelete ? deleteSessionDirect($event) : null",
					@assignMembers="caps.canAssignMembers ? openAssignModal($event) : null")
			#session-editor-wrapper(v-if="editorSession && caps.canEdit", @click="editorSession = null")
				form#session-editor(@click.stop="", @submit.prevent="editorSave")
					h3.session-editor-title(v-if="editorSession.code")
						a(v-if="caps.showSubmissionLinks && organizerSlug && eventSlug", :href="`${api.getOrgaEventBase()}/submissions/${editorSession.code}/`") {{ getLocalizedString(editorSession.title) }}
						span(v-else) {{ getLocalizedString(editorSession.title) }}
					.data
						.data-row(v-if="editorSession.code && editorSession.speakers && editorSession.speakers.length > 0 && caps.showSpeakers").form-group.row
							label.data-label.col-form-label.col-md-3 {{ $t('Speakers') }}
							.col-md-9.data-value
								span(v-for="speaker, index of editorSession.speakers")
									a(v-if="caps.showSubmissionLinks && organizerSlug && eventSlug && speaker.code", :href="`${api.getOrgaEventBase()}/speakers/${speaker.code}/`") {{ speaker.name || speaker.code }}
									span(v-else) {{ speaker.name }}
									span(v-if="index != editorSession.speakers.length - 1") {{', '}}
								span.text-warning(v-if="editorSession.speakers.some(s => !s.name)")  ({{ $t('some speakers have not shared their names') }})
						.data-row(v-else).form-group.row
							label.data-label.col-form-label.col-md-3 {{ $t('Title') }}
							.col-md-9
								.i18n-form-group
									template(v-for="locale of locales")
										input.form-control(v-model="editorSession.title[locale]", :required="true", :lang="locale", type="text")
						.data-row(v-if="editorSession.track && caps.showTracks").form-group.row
							label.data-label.col-form-label.col-md-3 {{ $t('Track') }}
							.col-md-9.data-value {{ getLocalizedString(editorSession.track.name) }}
						.data-row(v-if="editorSession.room").form-group.row
							label.data-label.col-form-label.col-md-3 {{ $t('Room') }}
							.col-md-9.data-value {{ getLocalizedString(editorSession.room.name) }}
						.data-row.form-group.row
							label.data-label.col-form-label.col-md-3 {{ $t('Duration') }}
							.col-md-9.number.input-group
								input.form-control(v-model="editorSession.duration", type="number", min="1", max="1440", step="1", :required="true")
								.input-group-append
									span.input-group-text {{ $t('minutes') }}
						.data-row(v-if="caps.canEditRoles").form-group.row
							label.data-label.col-form-label.col-md-3 {{ $t('Roles') }}
							.col-md-9
								.role-row(v-for="(r, index) in editorSession.roles" :key="index")
									select.form-control.role-select(v-model="r.id", required)
										option(:value="undefined" disabled) {{ $t('Select a role') }}
										option(v-for="role in schedule?.roles", :key="role.id", :value="role.id") {{ getLocalizedString(role.name) }}
									input.form-control.role-capacity(v-model.number="r.capacity", type="number", min="1", required, :title="$t('Capacity')")
									a.text-danger(href="#", @click.prevent="editorSession.roles.splice(index, 1)")
										i.fa.fa-trash
								a(href="#", @click.prevent="editorSession.roles.push({id: undefined, capacity: 1})")
									i.fa.fa-plus
									|  {{ $t('Add Role') }}


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
						bunt-button#btn-delete(v-if="caps.canEditRoles ? editorSession.id : !editorSession.code", @click="editorDelete", :loading="editorSessionWaiting") {{ $t('Delete') }}
						bunt-button#btn-save(@click="editorSave", :loading="editorSessionWaiting") {{ $t('Save') }}
			
			#assign-modal-wrapper(v-if="assigningSession && caps.canAssignMembers", @click="closeAssignModal")
				#session-editor(@click.stop="")
					h3.session-editor-title
						span {{ assignMembersHeading }}
						button.modal-close-btn(type="button", @click="closeAssignModal", :aria-label="$t('Close')")
							i.fa.fa-times(aria-hidden="true")
					
					.assign-modal-error(v-if="assignModalError")
						span {{ assignModalError }}
						button.assign-modal-error-dismiss(type="button", @click="assignModalError = ''", :aria-label="$t('Dismiss')")
							i.fa.fa-times(aria-hidden="true")
					
					.data.assign-data
						.assign-role(v-for="role in assigningSession.roles", :key="role.id")
							h4 {{ getLocalizedString(role.name) }} ({{ role.assigned.length }}/{{ role.capacity }} {{ $t('assigned') }})
							
							.assigned-list
								span.member-chip(v-for="user in role.assigned", :key="user.id")
									| {{ user.name }}
									button.member-chip-remove(type="button", @click="unassignMember(role.id, user.id)", :aria-label="$t('Unassign')", :title="$t('Unassign')")
										i.fa.fa-times(aria-hidden="true")
								p.text-muted(v-if="!role.assigned.length") {{ $t('No members assigned yet.') }}
							
							.assign-new.form-group.row
								.col-md-8
									select.form-control(v-model="selectedMemberIds[role.id]")
										option(:value="undefined" disabled) {{ $t('Select a member to assign') }}
										option(v-for="vol in availableMembersByRole[role.id]", :key="vol.id", :value="vol.id") {{ vol.name }}{{ vol.email ? ` (${vol.email})` : '' }}
								.col-md-4
									button.assign-btn(type="button", @click="assignMember(role.id)", :disabled="assigningWaiting") {{ $t('Assign') }}

		confirm-dialog(
			v-if="caps.showRoles",
			ref="confirmDialogRef",
			:title="confirmDialogTitle",
			:lead="confirmDialogLead",
			:confirm-label="confirmDialogLabel",
			:confirm-class="confirmDialogClass",
			:busy="confirmDialogBusy",
			:error="confirmDialogError",
			@confirm="onConfirmDialogConfirm",
			@cancel="onConfirmDialogCancel")

		dialog.break-confirm-dialog(ref="breakConfirmDialogEl", @click="onBreakDialogBackdrop", @cancel.prevent="cancelBreakDelete")
			.dialog-inner(@click.stop="")
				h3 {{ breakConfirmTitle }}
				p {{ breakConfirmLead }}
				p.break-confirm-error(v-if="breakConfirmError") {{ breakConfirmError }}
				.break-confirm-actions
					button.btn.btn-sm.btn-default(type="button", :disabled="breakConfirmBusy", @click="cancelBreakDelete") {{ $t('Cancel') }}
					button.btn.btn-sm.btn-danger(type="button", :disabled="breakConfirmBusy", @click="confirmBreakDelete") {{ $t('Delete') }}

	bunt-progress-circular(v-else, size="huge", :page="true")
</template>

<script lang="ts" setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted, onBeforeMount, nextTick } from 'vue'
import moment, { Moment } from 'moment-timezone'
import GridSchedule from '~/components/GridSchedule.vue'
import TalkSession from '~/components/Session.vue'
import ShiftSession from '~/teamshifts-adapter/Session.vue'
import ConfirmDialog from '~/teamshifts-adapter/ConfirmDialog.vue'
import api from '~/api'
import { resolveMode, getCapabilities } from '~/teamshifts-adapter'
import type { Capabilities } from '~/teamshifts-adapter/types'
import { getLocalizedString } from '~/utils'
import {translate as $t} from '~/lib/i18n'
import type { AvailabilityEntry, RoleAssignment, ScheduleRole } from '~/schemas';

interface Speaker {
  code?: string | null
  name: string
}

interface Track {
  id: string | number
  name: Record<string, string>
}

interface Room {
  id: string | number
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
  speakers?: string[]
  track?: string | number
  room?: string | number
  duration: number
  start?: string | null
  end?: string | null
  state?: string
  updated?: string
  submission?: Record<string, unknown>
  uncreated?: boolean
  availabilities?: AvailabilityEntry[]
  do_not_record?: boolean
  roles?: RoleAssignment[]
  role?: string | number
  capacity?: number
}

interface EditorRoleEntry {
  id?: number
  capacity: number
}

interface SessionData {
  id: number
  code?: string
  title: Record<string, string> | string
  abstract?: string
  speakers?: Speaker[]
  track?: Track
  duration?: number
  start?: Moment
  end?: Moment
  state?: string
  room?: Room
  deletedRoom?: boolean
  uncreated?: boolean
  availabilities?: AvailabilityEntry[]
  do_not_record?: boolean
  roles?: (RoleAssignment | EditorRoleEntry)[]
  role?: string | number
  capacity?: number
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
  roles?: ScheduleRole[]
}

const props = defineProps<{
  locale: string
}>()

const mode = resolveMode()
const caps: Capabilities = getCapabilities(mode)
const Session = mode === 'shifts' || mode === 'public-shifts' ? ShiftSession : TalkSession

const eventSlug = ref<string | null>(null)
const organizerSlug = ref<string | null>(null)
const scrollParentWidth = ref<number>(Infinity)
const schedule = ref<Schedule | null>(null)
const isUnassignedCollapsed = ref<boolean>(true)
const availabilities = reactive<{ rooms: Record<string, AvailabilityEntry[]>; talks: Record<string, AvailabilityEntry[]> }>({
  rooms: {},
  talks: {},
})
const availableMembersByRole = ref<Record<string, { id: number; name: string; email?: string }[]>>({})
const warnings = reactive<Record<string, Warning[]>>({})
const currentDay = ref<Moment | null>(null)
const draggedSession = ref<SessionData | null>(null)
const editorSession = ref<SessionData | null>(null)
const editorSessionWaiting = ref<boolean>(false)
const assigningSession = ref<SessionData | null>(null)
const assigningWaiting = ref<boolean>(false)
const assignModalError = ref<string>('')
const selectedMemberIds = ref<Record<string, number | undefined>>({})

const confirmDialogRef = ref<InstanceType<typeof ConfirmDialog> | null>(null)
const confirmDialogTitle = ref('')
const confirmDialogLead = ref('')
const confirmDialogLabel = ref('')
const confirmDialogClass = ref('btn-primary')
const confirmDialogBusy = ref(false)
const confirmDialogError = ref('')
let confirmDialogResolve: ((value: boolean) => void) | null = null
let confirmDialogAction: (() => Promise<void>) | null = null

const breakConfirmDialogEl = ref<HTMLDialogElement | null>(null)
const breakConfirmTitle = ref('')
const breakConfirmLead = ref('')
const breakConfirmError = ref('')
const breakConfirmBusy = ref(false)
let breakConfirmResolve: ((value: boolean) => void) | null = null
let breakDeleteId: number | null = null

function showBreakConfirmDialog(id: number): Promise<boolean> {
  breakDeleteId = id
  breakConfirmTitle.value = $t('Delete break')
  breakConfirmLead.value = $t('Are you sure you want to delete this break?')
  breakConfirmError.value = ''
  breakConfirmBusy.value = false
  return new Promise((resolve) => {
    breakConfirmResolve = resolve
    nextTick(() => breakConfirmDialogEl.value?.showModal?.())
  })
}

async function confirmBreakDelete() {
  if (!breakDeleteId) return
  breakConfirmBusy.value = true
  breakConfirmError.value = ''
  try {
    await api.deleteTalk({ id: breakDeleteId })
    if (schedule.value) {
      schedule.value.talks = schedule.value.talks.filter((s) => s.id !== breakDeleteId)
    }
    await fetchAdditionalScheduleData()
    breakConfirmDialogEl.value?.close()
    breakConfirmResolve?.(true)
  } catch (error) {
    breakConfirmError.value = $t('Failed to delete break. Please try again.')
    breakConfirmResolve?.(false)
  } finally {
    breakConfirmBusy.value = false
    breakConfirmResolve = null
    breakDeleteId = null
  }
}

function cancelBreakDelete() {
  breakConfirmDialogEl.value?.close()
  breakConfirmResolve?.(false)
  breakConfirmResolve = null
  breakDeleteId = null
}

function onBreakDialogBackdrop(event: MouseEvent) {
  if (event.target === breakConfirmDialogEl.value) cancelBreakDelete()
}

function showConfirmDialog(opts: { title: string; lead: string; confirmLabel: string; confirmClass?: string; onConfirm?: () => Promise<void> }): Promise<boolean> {
  confirmDialogTitle.value = opts.title
  confirmDialogLead.value = opts.lead
  confirmDialogLabel.value = opts.confirmLabel
  confirmDialogClass.value = opts.confirmClass || 'btn-primary'
  confirmDialogBusy.value = false
  confirmDialogError.value = ''
  confirmDialogAction = opts.onConfirm || null
  return new Promise((resolve) => {
    confirmDialogResolve = resolve
    nextTick(() => confirmDialogRef.value?.show())
  })
}

async function onConfirmDialogConfirm() {
  if (confirmDialogAction) {
    confirmDialogBusy.value = true
    confirmDialogError.value = ''
    try {
      await confirmDialogAction()
      confirmDialogRef.value?.close()
      confirmDialogResolve?.(true)
    } catch (error) {
      confirmDialogError.value = (error as Error).message || $t('An error occurred. Please try again.')
      confirmDialogResolve?.(false)
    } finally {
      confirmDialogBusy.value = false
      confirmDialogResolve = null
      confirmDialogAction = null
    }
  } else {
    confirmDialogRef.value?.close()
    confirmDialogResolve?.(true)
    confirmDialogResolve = null
    confirmDialogAction = null
  }
}

function onConfirmDialogCancel() {
  confirmDialogResolve?.(false)
  confirmDialogResolve = null
  confirmDialogAction = null
}
const isUnassigning = ref<boolean>(false)
const locales = ref<string[]>(['en'])
const unassignedFilterString = ref<string>('')
const unassignedSort = ref<string>('title')
const unassignedSortDirection = ref<number>(1)
const showUnassignedSortMenu = ref<boolean>(false)
const newBreakTooltip = ref<string>('')
const eventTimezone = ref<string | null>(null)
const since = ref<string | undefined>(undefined)
const showTimeDensityMenu = ref<boolean>(false)
const customDropdownRef = ref<HTMLElement | null>(null)

const condensedView = ref<boolean>(localStorage.getItem('schedule-editor-condensed') === '1')
const timeDensityMinutes = ref<number>(Number(localStorage.getItem('schedule-time-density-minutes') || 30))

const gridDensity = computed<'compact' | 'default' | 'comfortable'>(() => {
  return condensedView.value ? 'compact' : 'default'
})

function toggleCondensedView (): void {
  condensedView.value = !condensedView.value
  localStorage.setItem('schedule-editor-condensed', condensedView.value ? '1' : '0')
}

function onTimeDensityChange (): void {
  localStorage.setItem('schedule-time-density-minutes', String(timeDensityMinutes.value))
}


const translations = computed(() => ({
  filterSessions: caps.showRoles ? $t('Filter shifts') : $t('Filter sessions'),
  newBreak: $t('New break'),
}))

const assignMembersHeading = computed(() => {
  if (!assigningSession.value) return $t('Assign Members')
  return $t('Assign Members for {{title}}', {title: getLocalizedString(assigningSession.value.title)})
})

function lookupKey(value?: string | number | null): string {
  return value == null ? '' : String(value)
}

const roomsLookup = computed<Record<string, Room>>(() => {
  if (!schedule.value) return {}
  return schedule.value.rooms.reduce((acc, room) => {
    acc[lookupKey(room.id)] = room
    return acc
  }, {} as Record<string, Room>)
})

const tracksLookup = computed<Record<string, Track>>(() => {
  if (!schedule.value) return {}
  return schedule.value.tracks.reduce((acc, track) => {
    acc[lookupKey(track.id)] = track
    return acc
  }, {} as Record<string, Track>)
})

const speakersLookup = computed<Record<string, Speaker>>(() => {
  if (!schedule.value) return {}
  return schedule.value.speakers.reduce((acc, speaker) => {
    if (speaker.code) {
      acc[speaker.code] = speaker
    }
    return acc
  }, {} as Record<string, Speaker>)
})

function resolveSessionSpeakers(speakers?: string[]): Speaker[] {
  if (!speakers?.length) return []
  return speakers
    .map((speakerCode) => speakersLookup.value[speakerCode])
    .filter((speaker): speaker is Speaker => Boolean(speaker))
}

const unassignedSortMethods = computed<SortMethod[]>(() => {
  const sortMethods: SortMethod[] = [
    { label: $t('Title'), name: 'title' },
  ]
  if (caps.showSpeakers) {
    sortMethods.push({ label: $t('Speakers'), name: 'speakers' })
  }
  if (schedule.value && schedule.value.tracks.length > 1 && caps.showTracks) {
    sortMethods.push({ label: $t('Track'), name: 'track' })
  }
  sortMethods.push({ label: $t('Duration'), name: 'duration' })
  return sortMethods
})

const unscheduled = computed<SessionData[]>(() => {
  if (!schedule.value) return []
  let sessions: SessionData[] = []
  const isShifts = mode === 'shifts' || mode === 'public-shifts'
  for (const session of schedule.value.talks.filter((s) => isShifts ? !s.room : !s.start)) {
    sessions.push({
      id: session.id,
      code: session.code,
      title: session.title,
      abstract: session.abstract,
      speakers: resolveSessionSpeakers(session.speakers),
      track: tracksLookup.value[lookupKey(session.track)],
      duration: session.duration,
      state: session.state,
      do_not_record: session.do_not_record,
      roles: session.roles ?? [],
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

const deletedRoomSessions = computed<SessionData[]>(() => {
  if (!schedule.value) return []
  const isShifts = mode === 'shifts' || mode === 'public-shifts'
  if (isShifts) return []
  return schedule.value.talks
    .filter(
      (session) =>
        session.code &&
        session.start &&
        (!session.room || !roomsLookup.value[lookupKey(session.room)]),
    )
    .map((session) => ({
      id: session.id,
      code: session.code,
      title: session.title,
      abstract: session.abstract,
      start: moment(session.start),
      end: moment(session.end),
      duration: session.end ? moment(session.end).diff(moment(session.start), 'minutes') : session.duration,
      speakers: resolveSessionSpeakers(session.speakers),
      track: tracksLookup.value[lookupKey(session.track)],
      state: session.state,
      deletedRoom: true,
      do_not_record: session.do_not_record,
    }))
})

const sessions = computed<SessionData[]>(() => {
  if (!schedule.value) return []
  const dayStart = days.value[0]
  const dayEnd = days.value.at(-1)?.clone().endOf('day')
  if (!dayStart || !dayEnd) return []

  const filteredSessions = schedule.value.talks.filter(
    (s) =>
      s.start &&
      s.room &&
      roomsLookup.value[lookupKey(s.room)] &&
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
    speakers: resolveSessionSpeakers(session.speakers),
    track: tracksLookup.value[lookupKey(session.track)],
    state: session.state,
    room: roomsLookup.value[lookupKey(session.room)],
    do_not_record: session.do_not_record,
    roles: session.roles || [],
  }))

  sessionList.sort((a, b) => a.start!.diff(b.start!))
  return sessionList
})

const days = computed<Moment[]>(() => {
  if (!schedule.value) return []
  let firstDay = moment(schedule.value.event_start).startOf('day')
  let lastDay = moment(schedule.value.event_end).startOf('day')

  const startedTalks = schedule.value.talks
    .map((talk) => talk.start)
    .filter((start): start is string => typeof start === 'string')
    .map((start) => moment(start))
    .filter((start) => start.isValid())

  const endedTalks = schedule.value.talks
    .map((talk) => talk.end)
    .filter((end): end is string => typeof end === 'string')
    .map((end) => moment(end))
    .filter((end) => end.isValid())

  const talkDates = [...startedTalks, ...endedTalks]

  if (talkDates.length) {
    let earliestTalkDay = talkDates[0].clone().startOf('day')
    let latestTalkDay = talkDates[0].clone().startOf('day')

    for (const talkDay of talkDates.slice(1)) {
      const normalizedTalkDay = talkDay.clone().startOf('day')
      if (normalizedTalkDay.isBefore(earliestTalkDay)) {
        earliestTalkDay = normalizedTalkDay
      }
      if (normalizedTalkDay.isAfter(latestTalkDay)) {
        latestTalkDay = normalizedTalkDay
      }
    }

    if (earliestTalkDay.isBefore(firstDay)) {
      firstDay = earliestTalkDay
    }
    if (latestTalkDay.isAfter(lastDay)) {
      lastDay = latestTalkDay
    }
  }

  const daysArray: Moment[] = [firstDay]
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

async function fetchSchedule(options?: { since?: string; warnings?: boolean }): Promise<Schedule> {
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

async function saveTalk(session: Talk): Promise<void> {
  await api.saveTalk(session as any).then((response: any) => {
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

async function rescheduleSession(e: RescheduleEvent): Promise<void> {
  if (!schedule.value) return
  const movedSession = schedule.value.talks.find((s) => s.id === e.session.id)
  stopDragging()
  if (!movedSession) return
  movedSession.start = e.start as string
  movedSession.end = e.end as string
  movedSession.room = e.room.id
  await saveTalk(movedSession)
  await fetchAdditionalScheduleData()
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
  await fetchAdditionalScheduleData()
}

function editorStart(session: SessionData | Talk): void {
  const newEditorSession = { ...session } as SessionData
  if (caps.canEditRoles) {
    if (!newEditorSession.roles || newEditorSession.roles.length === 0) {
      newEditorSession.roles = [{ id: undefined, capacity: 1 }]
    } else {
      newEditorSession.roles = newEditorSession.roles.map((r) => ({ ...r }))
    }
  }
  editorSession.value = newEditorSession
}

async function editorSave(): Promise<void> {
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
    start: typeof editorSession.value.start === 'string' ? editorSession.value.start : editorSession.value.start?.toISOString(),
    end: typeof editorSession.value.end === 'string' ? editorSession.value.end : editorSession.value.end?.toISOString(),
    room: editorSession.value.room?.id,
    speakers: editorSession.value.speakers?.map(s => 
      typeof s === 'string' ? s : s.name
    ) || [],
    track: editorSession.value.track?.id,
    abstract: editorSession.value.abstract,
    state: editorSession.value.state
  }

  if (caps.canEditRoles) {
    talk.roles = editorSession.value.roles?.filter((r) => r.id !== undefined)
  }
  
  await saveTalk(talk)

  const sessionInSchedule = schedule.value?.talks.find((s) => s.id === editorSession.value?.id)
  if (sessionInSchedule && editorSession.value) {
    sessionInSchedule.end = typeof editorSession.value.end === 'string' ? editorSession.value.end : editorSession.value.end?.toISOString()
    if (!('submission' in sessionInSchedule)) {
      sessionInSchedule.title = editorSession.value.title as Record<string, string>
    }
  }
  
  if (caps.showRoles) {
    schedule.value = await fetchSchedule()
  }
  
  editorSessionWaiting.value = false
  editorSession.value = null
  await fetchAdditionalScheduleData()
}

async function editorDelete(): Promise<void> {
  if (!editorSession.value) return
  let deleted = false
  if (mode === 'shifts' || mode === 'public-shifts') {
    deleted = await deleteShiftById(editorSession.value.id)
  } else {
    if (editorSession.value.code) return
    deleted = await deleteTalkBreakById(editorSession.value.id)
  }
  if (deleted) {
    editorSession.value = null
  }
}

async function deleteSessionDirect(session: SessionData | Talk): Promise<void> {
  if (mode === 'shifts' || mode === 'public-shifts') {
    await deleteShiftById(session.id)
  } else {
    if (session.code) return
    await deleteTalkBreakById(session.id)
  }
}

async function deleteShiftById(id: number): Promise<boolean> {
  return showConfirmDialog({
    title: $t('Delete shift'),
    lead: $t('Are you sure you want to delete this shift? This action cannot be undone.'),
    confirmLabel: $t('Delete'),
    confirmClass: 'btn-danger',
    onConfirm: async () => {
      await api.deleteTalk({ id })
      if (schedule.value) {
        schedule.value.talks = schedule.value.talks.filter((s) => s.id !== id)
      }
      await fetchAdditionalScheduleData()
    },
  })
}

async function deleteTalkBreakById(id: number): Promise<boolean> {
  return showBreakConfirmDialog(id)
}

async function openAssignModal(session: SessionData | Talk): Promise<void> {
  assignModalError.value = ''
  assigningSession.value = { ...session } as SessionData
  if (assigningSession.value.roles && assigningSession.value.roles.length > 0) {
    for (const role of assigningSession.value.roles) {
      selectedMemberIds.value[String(role.id)] = undefined
    }
    await Promise.all(assigningSession.value.roles.map((role) => loadMembers(role.id)))
  }
}

function closeAssignModal(): void {
  assigningSession.value = null
  assignModalError.value = ''
  selectedMemberIds.value = {}
  availableMembersByRole.value = {}
}

async function loadMembers(roleId: number): Promise<void> {
  try {
    const response = await api.fetchMembers(roleId)
    availableMembersByRole.value[String(roleId)] = response.members ?? []
  } catch (error) {
    console.error('Failed to fetch members', error)
    assignModalError.value = $t('Failed to load members. Please try again.')
  }
}

async function assignMember(roleId: number): Promise<void> {
  const selectedMemberId = selectedMemberIds.value[String(roleId)]
  if (!assigningSession.value || !selectedMemberId) return
  
  assigningWaiting.value = true
  try {
    await api.assignMember(Number(assigningSession.value.id), roleId, selectedMemberId)
    
    const sched = await fetchSchedule({ warnings: true })
    if (schedule.value) {
      schedule.value.talks = sched.talks
      if (sched.roles) schedule.value.roles = sched.roles
      const updatedSession = sched.talks.find(t => t.id === assigningSession.value?.id)
      if (updatedSession) {
        assigningSession.value = { ...updatedSession } as SessionData
      }
    }
    await fetchAdditionalScheduleData()
    await loadMembers(roleId)
    selectedMemberIds.value[String(roleId)] = undefined
  } catch (error) {
    console.error('Failed to assign member', error)
    assignModalError.value = $t('Failed to assign member. Please try again.')
  } finally {
    assigningWaiting.value = false
  }
}

async function unassignMember(roleId: number, userId: number): Promise<void> {
  if (!assigningSession.value) return
  const confirmed = await showConfirmDialog({
    title: $t('Unassign member'),
    lead: $t('Are you sure you want to unassign this member?'),
    confirmLabel: $t('Unassign'),
    confirmClass: 'btn-danger',
  })
  if (!confirmed) return
  
  assigningWaiting.value = true
  try {
    await api.unassignMember(Number(assigningSession.value.id), roleId, userId)
    
    const sched = await fetchSchedule({ warnings: true })
    if (schedule.value) {
      schedule.value.talks = sched.talks
      if (sched.roles) schedule.value.roles = sched.roles
      const updatedSession = sched.talks.find(t => t.id === assigningSession.value?.id)
      if (updatedSession) {
        assigningSession.value = { ...updatedSession } as SessionData
      }
    }
    await fetchAdditionalScheduleData()
  } catch (error) {
    console.error('Failed to unassign member', error)
    assignModalError.value = $t('Failed to unassign member. Please try again.')
  } finally {
    assigningWaiting.value = false
  }
}

function showNewBreakHint() {
  newBreakTooltip.value = $t('Drag the box to the schedule to create a new break')
}

function removeNewBreakHint() {
  newBreakTooltip.value = ''
}

function onNewBreakKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    removeNewBreakHint()
  }
}

function onUnassignedLeave() {
  isUnassigning.value = false
  removeNewBreakHint()
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
  isUnassigning.value = false
  if (availabilities && availabilities.talks[session.id! ?? 0] && availabilities.talks[session.id! ?? 0].length !== 0) {
    session.availabilities = availabilities.talks[session.id! ?? 0]
  }
  draggedSession.value = session as SessionData
}

async function stopDragging(): Promise<void> {
  try {
    if (isUnassigning.value && draggedSession.value) {
      if (draggedSession.value.code && !draggedSession.value.deletedRoom) {
        const movedSession = schedule.value?.talks.find((s) => s.id === draggedSession.value!.id)
        if (movedSession) {
          if (mode === 'shifts' || mode === 'public-shifts') {
            movedSession.room = undefined
          } else {
            movedSession.start = null
            movedSession.end = null
            movedSession.room = undefined
          }
          await saveTalk(movedSession)
          await fetchAdditionalScheduleData()
        }
      } else if (schedule.value?.talks.find((s) => s.id === draggedSession.value!.id)) {
        schedule.value.talks = schedule.value.talks.filter((s) => s.id !== draggedSession.value!.id)
        await api.deleteTalk({ id: Number(draggedSession.value.id) })
        await fetchAdditionalScheduleData()
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
    await fetchAdditionalScheduleData()
  }
  since.value = sched.now || schedule.value.now
  window.setTimeout(pollUpdates, 10 * 125)
}

onBeforeMount(async () => {
  schedule.value = await fetchSchedule()
  eventTimezone.value = schedule.value.timezone
  moment.tz.setDefault(eventTimezone.value)
  locales.value = schedule.value.locales
  const match = window.location.pathname.match(/\/orga\/event\/([^/]+)\/([^/]+)/);
  organizerSlug.value = match ? match[1] : null;
  eventSlug.value = match ? match[2] : null;
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

const onStorageChange = (e: StorageEvent) => {
  if (e.key === 'schedule-time-density-minutes' && e.newValue) {
    timeDensityMinutes.value = Number(e.newValue)
  }
  if (e.key === 'schedule-editor-condensed') {
    condensedView.value = e.newValue === '1'
  }
}

const onWindowClick = (e: MouseEvent) => {
  if (showTimeDensityMenu.value && customDropdownRef.value && !customDropdownRef.value.contains(e.target as Node)) {
    showTimeDensityMenu.value = false
  }
}

const preventScrollOnDrag = (e: TouchEvent) => {
  if (draggedSession.value) {
    e.preventDefault()
  }
}

onMounted(() => {
  document.addEventListener('touchmove', preventScrollOnDrag, { passive: false })
  window.addEventListener('click', onWindowClick)
  window.addEventListener('resize', onWindowResize)
  window.addEventListener('storage', onStorageChange)
  onWindowResize()
})

onUnmounted(() => {
  document.removeEventListener('touchmove', preventScrollOnDrag)
  window.removeEventListener('click', onWindowClick)
  window.removeEventListener('resize', onWindowResize)
  window.removeEventListener('storage', onStorageChange)
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
	&.is-public-shifts
		#main-wrapper
			display: block
		#schedule-wrapper
			width: 100%
			margin-right: 0
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
		margin-bottom: 0
		flex: 1
		min-width: 0
		height: 48px
		max-height: 48px
		overflow-x: auto
		overflow-y: hidden
		scrollbar-width: thin
		.bunt-tabs
			height: 48px
		.bunt-tabs-header
			width: 100%
			min-width: max-content
			height: 48px
		.bunt-tabs-header-items
			display: flex
			flex-wrap: nowrap
			width: 100%
			min-width: max-content
			height: 48px
			margin: 0
			padding: 0
			.bunt-tab-header-item
				flex-shrink: 0
				white-space: nowrap
				height: 48px
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
		.unassigned-header
			position: sticky
			top: 0
			z-index: 10
			background-color: $clr-white
			padding-bottom: 8px
			display: flex
			flex-direction: column
			

		.unassigned-header > .density-controls
			display: flex
			align-items: center
			justify-content: flex-start
			gap: 12px
			padding: 0 8px
			margin-bottom: 12px
			.select-wrapper.custom-dropdown
				position: relative
				display: flex
				align-items: center
				background-color: transparent
				border: 1px solid #999
				border-radius: 4px
				padding: 4px 28px 4px 10px
				color: #333
				cursor: pointer
				font-size: 14px
				font-weight: 500
				line-height: 1.2
				transition: all 0.15s ease
				&:hover
					background-color: #f3f4f6
				.fa-chevron-down
					position: absolute
					right: 8px
					pointer-events: none
					font-size: 12px
					color: #333
				.time-density-menu, .vue-dropdown
					position: absolute
					top: calc(100% + 4px)
					right: 0
					background-color: white
					border-radius: 4px
					box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)
					border: 1px solid #e5e7eb
					z-index: 1000
					min-width: 120px
					display: flex
					flex-direction: column
					overflow: hidden
					cursor: default
					.density-option
						padding: 8px 12px
						display: flex
						justify-content: space-between
						align-items: center
						color: #374151
						cursor: pointer
						&:hover
							background-color: #f3f4f6
						&.active
							background-color: #e5e7eb
							color: #111
						.fa-check
							font-size: 12px
							color: var(--color-primary, #3b82f6)
			.density-btn
				background: none
				border: 1px solid #999
				border-radius: 4px
				padding: 4px 10px
				cursor: pointer
				color: #333
				display: flex
				align-items: center
				justify-content: center
				transition: all 0.15s ease
				font-size: 14px
				font-weight: 500
				&:hover
					background-color: #f3f4f6
				&:focus-visible
					outline: 2px solid var(--color-primary, #3b82f6)
					outline-offset: -1px
					background-color: #f3f4f6
				&.active
					background-color: #e5e7eb
					color: #111
					border-color: #6b7280
					box-shadow: inset 0 2px 4px rgba(0,0,0,0.05)
				.fa
					font-size: 14px
				.density-btn-text
					margin-left: 6px
					font-weight: 500
					white-space: nowrap
		.unassigned-header > .title
			position: relative
			padding: 4px 0
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
			&:focus-visible
				outline: 2px solid var(--color-primary, #3b82f6)
				outline-offset: 2px
		.new-break.c-linear-schedule-session.small-break
			display: none
		.new-break.c-linear-schedule-session.desktop-break
			display: flex
		.new-break-hint
			display: block
			background: rgba(0, 0, 0, 0.6)
			color: white
			font-size: 13px
			line-height: 1.4
			padding: 6px 10px
			border-radius: 4px
			pointer-events: none
			margin: 0 12px 8px 8px
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
			text-align: left
			.sort-method
				padding: 8px 16px
				display: flex
				justify-content: space-between
				align-items: center
				&:hover
					background-color: $clr-dividers-light
		.deleted-room-sessions
			margin: 24px 12px 0 8px
			padding-top: 16px
			border-top: 4px solid $clr-danger
			h3
				margin: 0 0 8px
				font-size: 18px
				font-weight: 600
				color: $clr-danger
			p
				margin: 0 8px 8px 0
				font-size: 13px
				line-height: 18px
				color: $clr-secondary-text-light
	.schedule-controls
		display: flex
		align-items: center
		justify-content: flex-start
		position: sticky
		left: 0
		top: 0
		z-index: 50
		background-color: $clr-white
		width: 100%
		height: 48px
		max-height: 48px
		box-sizing: border-box
		overflow: hidden
	#schedule-wrapper
		flex: 1
		min-height: 0
		min-width: 0
		width: 100%
		margin-right: 40px
	#unassigned
		.unassigned-mobile-header
			display: none
			@media (max-width: 767px)
				display: flex
				align-items: center
				justify-content: space-between
				padding: 10px 14px
				background-color: #f8fafc
				border: 1px solid #cbd5e1
				border-radius: 6px
				margin-bottom: 8px
				cursor: pointer
				user-select: none
				.unassigned-title
					display: flex
					align-items: center
					gap: 8px
					font-weight: 600
					font-size: 14px
					color: #1e293b
					.drop-hint
						color: var(--color-primary, #2185d0)
						font-weight: normal
				.unassigned-collapse-icon
					color: #64748b
					font-size: 14px

@media (max-width: 767px)
	.pretalx-schedule
		margin-left: 0
		margin-right: 0
		padding: 0 12px
		width: 100%
		box-sizing: border-box
		min-height: calc(100vh - 160px)
		#main-wrapper
			flex-direction: column
			width: 100%
			box-sizing: border-box
		#unassigned
			width: 100%
			box-sizing: border-box
			margin-top: 0
			margin-bottom: 12px
			background-color: $clr-white
			padding-top: 8px
			padding-bottom: 4px
			flex: none
			&.is-collapsed
				.unassigned-body
					display: none
			.unassigned-body
				max-height: 300px
				overflow-y: auto
				padding-bottom: 8px
				border-bottom: 1px solid #e2e8f0
				margin-bottom: 8px
				box-sizing: border-box
			> *
				margin-right: 0
			.c-linear-schedule-session
				margin: 8px 0
				width: 100%
				min-width: 0
				box-sizing: border-box
			.unassigned-header
				width: 100%
				box-sizing: border-box
				> .density-controls
					flex-wrap: nowrap
					align-items: center
					width: 100%
					box-sizing: border-box
					.density-btn
						padding: 4px 8px
						.density-btn-text
							display: none
					.small-break.c-linear-schedule-session
						display: inline-flex
						align-items: center
						justify-content: center
						margin-left: auto
						margin-top: 0
						margin-bottom: 0
						margin-right: 0
						height: 30px
						min-height: 30px
						max-height: 30px
						padding: 0 12px
						background: #f1f5f9
						border: 1px solid #94a3b8
						border-radius: 6px
						color: #0f172a
						font-weight: 600
						font-size: 13px
						cursor: grab
						user-select: none
						box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05)
						transition: all 0.15s ease
						box-sizing: border-box
						flex-shrink: 0
						min-width: 0
						width: auto
						&:hover, &:active
							background: #e2e8f0
							border-color: var(--color-primary, #2185d0)
							color: var(--color-primary, #2185d0)
						.time-box
							display: none
						.info
							display: flex
							align-items: center
							padding: 0
							margin: 0
							.title-row
								display: flex
								align-items: center
								.title
									font-size: 13px
									font-weight: 600
									color: inherit
									white-space: nowrap
									overflow: hidden
									text-overflow: ellipsis
									max-width: 120px
			.desktop-break.c-linear-schedule-session
				display: none
		#schedule-wrapper
			width: 100%
			margin-right: 0
			box-sizing: border-box
			overflow: auto

#session-editor-wrapper, #assign-modal-wrapper
	position: fixed
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
		width: min(680px, 95vw)
		max-width: 95vw
		max-height: calc(100vh - 48px)
		overflow-y: auto

		.session-editor-title
			font-size: 22px
			margin-bottom: 16px
			display: flex
			justify-content: space-between
			align-items: center
			.modal-close-btn
				background: none
				border: none
				font-size: 20px
				color: #666
				cursor: pointer
				padding: 4px 8px
				line-height: 1
				border-radius: 4px
				&:hover
					color: #333
					background-color: rgba(0, 0, 0, 0.05)
		.button-row
			display: flex
			width: 100%
			margin-top: 24px

			.bunt-button-content
				font-size: 16px
			#btn-delete
				button-style(color: $clr-danger, text-color: $clr-white)
				font-weight: bold
			#btn-save
				margin-left: auto
				font-weight: bold
				button-style(color: #2185d0)
			[type="submit"]
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
			.input-group
				position: relative
				display: flex
				flex-wrap: wrap
				align-items: stretch
				> input
					flex: 1 1 auto
					width: 1%
					min-width: 0
					border-top-right-radius: 0
					border-bottom-right-radius: 0
			.input-group-append
				display: flex
				margin-left: -1px
			.input-group-text
				display: flex
				align-items: center
				padding: 0.375rem 0.75rem
				color: var(--color-text-input)
				white-space: nowrap
				background-color: var(--color-grey-lighter)
				border: 1px solid var(--color-border)
				border-top-right-radius: var(--size-border-radius)
				border-bottom-right-radius: var(--size-border-radius)
			.role-row
				display: flex
				align-items: center
				gap: 10px
				margin-bottom: 10px
				.role-select
					flex: auto
				.role-capacity
					flex: none
					width: 100px
		.warning
			color: #b23e65
		.assign-data
			.assign-role
				margin-bottom: 24px
			.assign-new
				align-items: center
		.assign-modal-error
			display: flex
			align-items: center
			justify-content: space-between
			gap: 8px
			padding: 10px 14px
			margin-bottom: 16px
			background-color: #fdecea
			border: 1px solid #f5c6cb
			border-radius: 4px
			color: #721c24
			font-size: 14px
			.assign-modal-error-dismiss
				background: none
				border: none
				color: #721c24
				cursor: pointer
				padding: 2px 6px
				font-size: 14px
				&:hover
					opacity: 0.7
		.member-chip
			display: inline-flex
			align-items: center
			gap: 6px
			background-color: $clr-grey-200
			color: $clr-primary-text-light
			border-radius: 14px
			padding: 4px 6px 4px 12px
			margin: 0 6px 6px 0
			font-size: 13px
			line-height: 1.4
			.member-chip-remove
				display: inline-flex
				align-items: center
				justify-content: center
				width: 18px
				height: 18px
				border: none
				border-radius: 50%
				background: none
				color: $clr-danger
				cursor: pointer
				padding: 0
				font-size: 11px
				&:hover
					background-color: rgba(0, 0, 0, 0.08)
		.assign-btn
			width: 100%
			height: 100%
			min-height: 38px
			border: none
			border-radius: 4px
			background-color: #2185d0
			color: $clr-white
			font-weight: bold
			cursor: pointer
			&:hover
				background-color: #1c71b1
			&:disabled
				opacity: 0.6
				cursor: default
.break-confirm-dialog
	border: none
	border-radius: 4px
	padding: 0
	max-width: 400px
	box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2)
	&::backdrop
		background: rgba(0, 0, 0, 0.5)
	.dialog-inner
		padding: 32px 40px
		h3
			margin: 0 0 12px
			font-size: 18px
		p
			margin: 0 0 16px
			color: $clr-grey-700
			line-height: 1.4
		.break-confirm-error
			color: $clr-danger
			margin: 0 0 12px
		.break-confirm-actions
			display: flex
			justify-content: flex-end
			gap: 8px
			.btn
				display: inline-block
				padding: 6px 12px
				font-size: 14px
				line-height: 1.4
				border-radius: 4px
				border: 1px solid transparent
				cursor: pointer
				&:disabled
					opacity: 0.65
					cursor: default
			.btn-default
				background: $clr-white
				border-color: $clr-dividers-light
				color: $clr-grey-900
			.btn-danger
				button-style(color: $clr-danger, text-color: $clr-white)
</style>

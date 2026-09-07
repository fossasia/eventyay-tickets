<template lang="pug">
.c-linear-schedule-session.is-shift-session(:style="style", @pointerdown.stop="onPointerDown", :class="classes")
	.time-box
		.start(:class="{'has-ampm': startTime?.ampm}", v-if="startTime")
			.time {{ startTime.time }}
			.ampm(v-if="startTime.ampm") {{ startTime.ampm }}
		.duration {{ durationPretty }}
	.info
		.title-row(style="display: flex; justify-content: space-between; align-items: flex-start;")
			.title(:class="{'title-clamped': isShortSession}") {{ getLocalizedString(session.title) }}
			.card-actions(v-if="caps.canEdit && !isBreak && session.room")
				button.btn.btn-link.p-0.mr-2(type="button", @pointerdown.stop, @click.stop="$emit('editSession', session)", :aria-label="$t('Edit')", :title="$t('Edit')")
					i.fa.fa-pencil(aria-hidden="true")
				button.btn.btn-link.p-0.text-danger(type="button", @pointerdown.stop, @click.stop="$emit('deleteSession', session)", :aria-label="$t('Delete')", :title="$t('Delete')")
					i.fa.fa-trash(aria-hidden="true")

		.roles-list(v-if="session.roles && session.roles.length")
			.role-item(v-for="role in session.roles", :key="role.id")
				.role-header
					span.role-name
						| {{ getLocalizedString(role.name) }}
						span.role-restricted-tag(v-if="role.is_restricted", :title="$t('Volunteers cannot self-claim this role; requires manual assignment.')") {{ $t('Restricted') }}
					span.role-badge(:class="getCapacityClass(role)") {{ role.assigned.length }}/{{ role.capacity }} {{ $t('assigned') }}
				.role-assignees
					template(v-if="role.assigned.length")
						span.role-assignee(v-for="(user, i) in previewAssignees(role)", :key="user.id || i")
							svg.role-user-icon(viewBox="0 0 24 24", aria-hidden="true")
								path(fill="currentColor", d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z")
							span.role-assignee-name {{ user.name }}
						.role-assignees-more-wrap(v-if="hiddenAssigneeCount(role)")
							button.role-assignees-more(
								type="button",
								:aria-expanded="openAssigneesRoleId != null ? 'true' : 'false'",
								@click.stop="toggleAssigneesPopover(role, $event)",
								@pointerdown.stop="") +{{ hiddenAssigneeCount(role) }} more
					span.text-muted(v-else) {{ $t('None') }}

		template(v-if="caps.showClaimUI")
			.shift-manage.mt-2(v-if="!isBreak")
				template(v-if="isMyClaimed")
					span.role-badge.badge-full.mr-2 {{ $t('Signed up') }}
					form.ts-inline-form(:action="withdrawUrl", method="post")
						input(type="hidden", name="csrfmiddlewaretoken", :value="csrfToken")
						button.btn.btn-sm.btn-danger(type="submit", @click.stop, @pointerdown.stop) {{ $t('Drop shift') }}
				template(v-else-if="hasClaimableSlot")
					form.ts-inline-form(:action="claimUrl", method="post")
						input(type="hidden", name="csrfmiddlewaretoken", :value="csrfToken")
						button.btn.btn-sm.btn-primary(type="submit", @click.stop, @pointerdown.stop) {{ $t('Sign Up') }}
				template(v-else)
					span.text-muted(style="font-size:11px") {{ $t('Full / Restricted') }}

		.shift-manage.mt-2.text-right(v-else-if="caps.canAssignMembers && !isBreak && session.room")
			button.btn.btn-sm.btn-assign-members(type="button", @pointerdown.stop, @click.stop="$emit('assignMembers', session)") {{ session.roles?.some(r => r.assigned.length < r.capacity) ? $t('Assign Members') : $t('Manage') }}

	.warning.no-print(v-if="warnings?.length")
		.warning-icon.text-danger
			span(v-if="warnings.length > 1") {{ warnings.length }}
			i.fa.fa-exclamation-triangle
	assignees-popover(
		:open="openAssigneesRoleId != null",
		:title="assigneesPopoverTitle",
		:assignees="assigneesPopoverList",
		:top="assigneesPopoverPos.top",
		:left="assigneesPopoverPos.left",
		:width="assigneesPopoverPos.width",
		:max-height="assigneesPopoverPos.maxHeight")
</template>

<script lang="ts" setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import moment, { Moment } from 'moment-timezone'
import { getLocalizedString } from '~/utils'
import { getCapabilities, resolveMode, resolveSessionKind, getClaimedShiftIds, getCsrfToken, getClaimBaseUrl } from '~/teamshifts-adapter'
import type { Capabilities } from '~/teamshifts-adapter/types'
import type { RoleAssignment } from '~/schemas'
import AssigneesPopover from '~/teamshifts-adapter/AssigneesPopover.vue'

const ASSIGNEE_PREVIEW_LIMIT = 2

function placeAssigneesPopover(anchorEl: HTMLElement) {
  const rect = anchorEl.getBoundingClientRect()
  const width = Math.min(280, Math.max(200, window.innerWidth - 16))
  const maxHeight = Math.min(280, window.innerHeight - 16)
  let left = rect.left
  let top = rect.bottom + 6
  if (left + width > window.innerWidth - 8) left = window.innerWidth - width - 8
  if (left < 8) left = 8
  if (top + 140 > window.innerHeight) {
    top = Math.max(8, rect.top - 6 - Math.min(maxHeight, 200))
  }
  return { top, left, width, maxHeight }
}

interface Speaker {
  name: string
  code?: string
  [key: string]: string | undefined
}

interface Track {
  name: string | Record<string, string>
  color?: string
  id?: number | string
  [key: string]: string | number | Record<string, string> | undefined
}

interface Session {
  id: number | string
  title: string | Record<string, string>
  speakers?: Speaker[]
  state?: string
  track?: Track
  start?: Moment
  end?: Moment
  code?: string | null
  duration: number
  abstract?: string
  room?: string | number
  do_not_record?: boolean
  roles?: RoleAssignment[]
  [key: string]: string | number | boolean | Record<string, string> | Speaker[] | Track | Moment | RoleAssignment[] | null | undefined
}

interface Warning {
  message: string
  type?: string
  [key: string]: string | undefined
}

const props = defineProps<{
  session: Session
  warnings?: Warning[]
  isDragged?: boolean
  isDragClone?: boolean
  overrideStart?: Moment | null
}>()

const emit = defineEmits<{
  (e: 'startDragging', payload: { session: Session; event: PointerEvent }): void
  (e: 'editSession', payload: Session): void
  (e: 'deleteSession', payload: Session): void
  (e: 'assignMembers', payload: Session): void
}>()

const mode = resolveMode()
const caps: Capabilities = getCapabilities(mode)
const isBreak = computed(() => resolveSessionKind(mode, props.session) === 'break')

const claimedShiftIds = computed(() => caps.showClaimUI ? getClaimedShiftIds() : new Set<number>())
const isMyClaimed = computed(() => claimedShiftIds.value.has(Number(props.session.id)))

const hasClaimableSlot = computed(() => {
  if (!props.session.roles?.length) return false
  return props.session.roles.some(
    (r) => !r.is_restricted && r.assigned.length < r.capacity
  )
})

const claimUrl = computed(() => {
  const base = getClaimBaseUrl()
  return base ? `${base}${props.session.id}/claim/` : ''
})

const withdrawUrl = computed(() => {
  const base = getClaimBaseUrl()
  return base ? `${base}${props.session.id}/withdraw/` : ''
})

const csrfToken = computed(() => caps.showClaimUI ? getCsrfToken() : '')

const getCapacityClass = (role: RoleAssignment) => {
  if (role.assigned.length >= role.capacity) return 'badge-full'
  if (role.assigned.length === 0) return 'badge-empty'
  return 'badge-partial'
}

const openAssigneesRoleId = ref<number | string | null>(null)
const assigneesPopoverList = ref<Array<{ id?: number | string; name: string }>>([])
const assigneesPopoverTitle = ref('Assigned')
const assigneesPopoverPos = ref({ top: 0, left: 0, width: 260, maxHeight: 280 })

const previewAssignees = (role: RoleAssignment) => role.assigned.slice(0, ASSIGNEE_PREVIEW_LIMIT)
const hiddenAssigneeCount = (role: RoleAssignment) => Math.max(0, role.assigned.length - ASSIGNEE_PREVIEW_LIMIT)

const closeAssigneesPopover = () => {
  openAssigneesRoleId.value = null
  assigneesPopoverList.value = []
}

const toggleAssigneesPopover = (role: RoleAssignment, event: MouseEvent) => {
  const roleId = role.id
  if (openAssigneesRoleId.value === roleId) {
    closeAssigneesPopover()
    return
  }
  assigneesPopoverList.value = role.assigned
  assigneesPopoverTitle.value = `Assigned (${role.assigned.length})`
  assigneesPopoverPos.value = placeAssigneesPopover(event.currentTarget as HTMLElement)
  openAssigneesRoleId.value = roleId
}

const onAssigneesDocPointerDown = (event: PointerEvent) => {
  if (openAssigneesRoleId.value == null) return
  const path = event.composedPath?.() || []
  const inside = path.some((node) => {
    const el = node as HTMLElement
    return el?.classList?.contains?.('role-assignees-popover') || el?.classList?.contains?.('role-assignees-more')
  })
  if (inside) return
  closeAssigneesPopover()
}

const onScroll = () => {
  if (openAssigneesRoleId.value != null) closeAssigneesPopover()
}

onMounted(() => {
  document.addEventListener('pointerdown', onAssigneesDocPointerDown, true)
  window.addEventListener('scroll', onScroll, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onAssigneesDocPointerDown, true)
  window.removeEventListener('scroll', onScroll, true)
})

const classes = computed(() => {
  const cls: string[] = ['istalk']

  if (props.session.state === 'pending') {
    cls.push('pending')
  } else if (
    props.session.state &&
    props.session.state !== 'confirmed' &&
    props.session.state !== 'accepted'
  ) {
    cls.push('unconfirmed')
  }

  if (props.isDragged) cls.push('dragging')
  if (props.isDragClone) cls.push('clone')
  if (isShortSession.value) cls.push('short-session')

  return cls
})

const style = computed(() => {
  let trackColor = '#c9920a'

  if (props.session.roles && props.session.roles.length > 0) {
    let allFull = true
    let anyEmpty = false
    for (const role of props.session.roles) {
      const capacity = role.capacity || 0
      if (capacity <= 0) continue
      const assigned = role.assigned?.length || 0
      if (assigned === 0) {
        anyEmpty = true
        break
      }
      if (assigned < capacity) {
        allFull = false
      }
    }
    if (anyEmpty) {
      trackColor = '#dc3545'
    } else if (allFull) {
      trackColor = '#28a745'
    } else {
      trackColor = '#c9920a'
    }
  }

  return { '--track-color': trackColor }
})

const startTime = computed<{ time: string; ampm?: string } | undefined>(() => {
  const time: Moment | undefined = props.overrideStart || props.session.start
  if (!time) return undefined

  if (moment.localeData().longDateFormat('LT').endsWith(' A')) {
    return {
      time: time.format('h:mm'),
      ampm: time.format('A'),
    }
  } else {
    return { time: time.format('LT') }
  }
})

const durationMinutes = computed<number>(() => {
  if (!props.session.start || !props.session.end) return props.session.duration
  return moment(props.session.end).diff(props.session.start, 'minutes')
})

const isShortSession = computed<boolean>(() => {
  const minutes = durationMinutes.value
  return minutes > 0 && minutes <= 15
})

const durationPretty = computed<string | undefined>(() => {
  const minutes = durationMinutes.value
  if (!minutes) return undefined

  if (minutes <= 60) {
    return `${minutes}min`
  }
  const hours = Math.floor(minutes / 60)
  const leftoverMinutes = minutes % 60
  if (leftoverMinutes) {
    return `${hours}h${leftoverMinutes}min`
  }
  return `${hours}h`
})

function onPointerDown(event: PointerEvent): void {
  if (!event.isPrimary || event.button !== 0) return
  const el = event.target as HTMLElement
  if (el && el.releasePointerCapture) {
    try { el.releasePointerCapture(event.pointerId) } catch (_) {}
  }
  emit('startDragging', { session: props.session, event })
}
</script>

<style lang="stylus">
.c-linear-schedule-session.is-shift-session
	.roles-list
		display: flex
		flex-direction: column
		gap: 6px
		margin-top: 6px
		.role-item
			border-top: 1px solid $clr-dividers-light
			padding-top: 6px
			.role-header
				display: flex
				justify-content: space-between
				align-items: center
				font-size: 13px
				font-weight: 600
				.role-restricted-tag
					margin-left: 6px
					font-size: 10px
					font-weight: 700
					text-transform: uppercase
					letter-spacing: 0.02em
					padding: 1px 5px
					border-radius: 3px
					background-color: #6c757d
					color: $clr-white
				.role-badge
					font-size: 11px
					font-weight: 600
					line-height: 1.3
					padding: 3px 8px
					border-radius: 999px
					border: 1.5px solid
					box-sizing: border-box
					white-space: nowrap
					&.badge-full
						border-color: #28a745
						color: #28a745
					&.badge-empty
						border-color: #dc3545
						color: #dc3545
					&.badge-partial
						border-color: #c9920a
						color: #c9920a
			.role-assignees
				position: relative
				display: flex
				flex-wrap: wrap
				align-items: center
				gap: 6px 12px
				font-size: 12px
				color: $clr-secondary-text-light
				margin-top: 4px
				.role-assignee
					display: inline-flex
					align-items: center
					gap: 6px
					min-width: 0
				.role-assignee-name
					min-width: 0
				.role-user-icon
					width: 11px
					height: 11px
					flex-shrink: 0
				.role-assignees-more-wrap
					position: relative
				.role-assignees-more
					border: none
					background: transparent
					color: var(--color-primary, #2185d0)
					font-size: 12px
					font-weight: 600
					line-height: 1.3
					padding: 0
					cursor: pointer
					&:hover
						text-decoration: underline
	.shift-manage
		font-size: 12px
		.btn
			padding: 2px 8px
			font-size: 12px
		.btn-assign-members
			background-color: #2185d0
			border-color: #2185d0
			color: #fff
			font-weight: 500
			padding: 4px 12px
			border-radius: 4px
			cursor: pointer
			&:hover
				background-color: #1a6fb5
				border-color: #1a6fb5
	.ts-inline-form
		display: inline
</style>

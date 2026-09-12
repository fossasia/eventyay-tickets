import type { Mode, Capabilities, ApiConfig, SessionKind } from './types'

export type { Mode, Capabilities, ApiConfig, SessionKind }

const basePath = process.env.BASE_PATH || ''

function getDataAttribute(attr: string): string {
  if (typeof window === 'undefined') return ''
  const el = document.querySelector('#app') as HTMLElement | null
  return el?.dataset?.[attr] ?? ''
}

export function resolveMode(): Mode {
  const dataMode = getDataAttribute('mode')
  if (dataMode === 'public-shifts') return 'public-shifts'
  if (dataMode === 'shifts') return 'shifts'
  if (typeof window !== 'undefined' && window.location.pathname.includes('/teamshifts/')) {
    return 'shifts'
  }
  return 'talks'
}

export function getCapabilities(mode?: Mode): Capabilities {
  const m = mode ?? resolveMode()
  switch (m) {
    case 'public-shifts':
      return {
        canDrag: false,
        canCreateBreak: false,
        canEdit: false,
        canDelete: false,
        canAssignMembers: false,
        canEditRoles: false,
        showSpeakers: false,
        showTracks: false,
        showRoles: true,
        showClaimUI: true,
        showSubmissionLinks: false,
        allowOverlap: true,
      }
    case 'shifts':
      return {
        canDrag: true,
        canCreateBreak: false,
        canEdit: true,
        canDelete: true,
        canAssignMembers: true,
        canEditRoles: true,
        showSpeakers: false,
        showTracks: false,
        showRoles: true,
        showClaimUI: false,
        showSubmissionLinks: false,
        allowOverlap: true,
      }
    case 'talks':
    default:
      return {
        canDrag: true,
        canCreateBreak: true,
        canEdit: true,
        canDelete: true,
        canAssignMembers: false,
        canEditRoles: false,
        showSpeakers: true,
        showTracks: true,
        showRoles: false,
        showClaimUI: false,
        showSubmissionLinks: true,
        allowOverlap: false,
      }
  }
}

export function getApiConfig(mode?: Mode): ApiConfig {
  const m = mode ?? resolveMode()

  if (m === 'public-shifts') {
    const match = window.location.pathname.match(/\/([^/]+)\/([^/]+)\/teamshifts\//)
    if (!match) {
      throw new Error('Public shift schedule must be loaded under /<organizer>/<event>/teamshifts/')
    }
    const baseUrl = `${basePath}/${match[1]}/${match[2]}/teamshifts`
    return {
      baseUrl,
      endpoints: {
        talks: '/shifts/api/',
        availabilities: '/schedule/api/availabilities/',
        warnings: '/schedule/api/warnings/',
        members: '/schedule/api/members/',
        assignments: '/schedule/api/assignments/',
      },
    }
  }

  const match = window.location.pathname.match(/\/event\/([^/]+)\/([^/]+)/)
  if (!match) {
    throw new Error('Schedule editor must be loaded under /orga/event/<organizer>/<event>/ or /teamshifts/event/<organizer>/<event>/')
  }

  const prefix = m === 'shifts' ? '/teamshifts' : '/orga'
  const baseUrl = `${basePath}${prefix}/event/${match[1]}/${match[2]}`

  if (m === 'shifts') {
    return {
      baseUrl,
      endpoints: {
        talks: '/schedule/api/shifts/',
        availabilities: '/schedule/api/availabilities/',
        warnings: '/schedule/api/warnings/',
        members: '/schedule/api/members/',
        assignments: '/schedule/api/assignments/',
      },
    }
  }

  return {
    baseUrl,
    endpoints: {
      talks: '/schedule/api/talks/',
      availabilities: '/schedule/api/availabilities/',
      warnings: '/schedule/api/warnings/',
      members: '',
      assignments: '',
    },
  }
}

export function getClaimedShiftIds(): Set<number> {
  const raw = getDataAttribute('claimedShifts')
  if (!raw) return new Set()
  try {
    return new Set(JSON.parse(raw) as number[])
  } catch {
    return new Set()
  }
}

export function getCsrfToken(): string {
  return getDataAttribute('csrfToken')
}

export function getClaimBaseUrl(): string {
  return getDataAttribute('claimBaseUrl')
}

export function resolveSessionKind(mode: Mode, session: { code?: string | null }): SessionKind {
  if (mode === 'shifts' || mode === 'public-shifts') return 'shift'
  if (session.code == null) return 'break'
  return 'talk'
}

import type { Moment } from 'moment-timezone'

interface Session {
  id: number | string
  room?: { id: number | string } | null
  start?: Moment | null
  end?: Moment | null
}

interface RoomLayout {
  colStart: number
  colSpan: number
}

function shiftSliceName(date: Moment): string {
  return `slice-${date.format('MM-DD-HH-mm')}`
}

export function computeRoomMaxOverlap(roomId: number | string, sessions: Session[]): number {
  const roomSessions = sessions
    .filter(s => s.room?.id === roomId && s.start && s.end)
    .sort((a, b) => {
      const diff = a.start!.diff(b.start!)
      return diff !== 0 ? diff : (a.id < b.id ? -1 : 1)
    })
  if (roomSessions.length <= 1) return 1
  let maxOverlap = 1
  for (let i = 0; i < roomSessions.length; i++) {
    let count = 1
    for (let j = i + 1; j < roomSessions.length; j++) {
      if (roomSessions[j].start!.isBefore(roomSessions[i].end!)) count++
    }
    if (count > maxOverlap) maxOverlap = count
  }
  return maxOverlap
}

export function computeShiftColumnLayout(
  rooms: { id: number | string }[],
  sessions: Session[]
): Map<number | string, RoomLayout> {
  const layout = new Map<number | string, RoomLayout>()
  let col = 2
  for (const room of rooms) {
    const span = computeRoomMaxOverlap(room.id, sessions)
    layout.set(room.id, { colStart: col, colSpan: span })
    col += span
  }
  return layout
}

export function buildShiftGridTemplateColumns(
  rooms: { id: number | string }[],
  sessions: Session[],
  minColWidth = '320px'
): string {
  const roomCols = rooms
    .map(room => {
      const span = computeRoomMaxOverlap(room.id, sessions)
      return Array(span).fill(`minmax(${minColWidth}, 1fr)`).join(' ')
    })
    .join(' ')
  return `78px ${roomCols} auto`
}

export function computeShiftOverlapSubcolumn(
  session: Session,
  allSessions: Session[],
  columnLayout: Map<number | string, RoomLayout>
): { gridRow: string; gridColumn: string } | null {
  if (!session.start || !session.end || !session.room) return null
  const roomLayout = columnLayout.get(session.room.id)
  if (!roomLayout || roomLayout.colSpan <= 1) return null

  const overlapping = allSessions
    .filter(s => {
      if (!s.room || !s.start || !s.end) return false
      if (s.room.id !== session.room!.id) return false
      return s.start.isBefore(session.end!) && s.end.isAfter(session.start!)
    })
    .sort((a, b) => {
      const diff = a.start!.diff(b.start!)
      return diff !== 0 ? diff : (a.id < b.id ? -1 : 1)
    })

  if (overlapping.length <= 1) return null

  const myIndex = overlapping.findIndex(s => s.id === session.id)
  const subCol = roomLayout.colStart + myIndex
  return {
    gridRow: `${shiftSliceName(session.start)} / ${shiftSliceName(session.end)}`,
    gridColumn: `${subCol} / ${subCol + 1}`,
  }
}

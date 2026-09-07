/**
 * Sidebar occupancy: live viewers for stages/rooms, lifetime participants for chat channels.
 */

const MEDIA_MODULE_TYPES = new Set([
	'livestream.native',
	'livestream.youtube',
	'call.bigbluebutton',
	'call.janus',
	'call.zoom',
	'call.jitsi',
	'networking.roulette',
	'page.landing',
])

function getModules(room) {
	return room?.module_config || room?.modules || []
}

function numericCount(value) {
	if (typeof value === 'number' && Number.isFinite(value)) return value
	if (typeof value === 'string' && value.trim() !== '') {
		const parsed = Number(value)
		if (Number.isFinite(parsed)) return parsed
	}
	return null
}

export function usesParticipantOccupancy(room) {
	const modules = getModules(room)
	if (!Array.isArray(modules) || !modules.length) return false
	return modules.some(module => module.type === 'chat.native') && !modules.some(module => MEDIA_MODULE_TYPES.has(module.type))
}

export function getRoomOccupancyCount(room, {
	rooms = [],
	activeRoomId = null,
	routeRoomId = null,
	roomViewers = null,
} = {}) {
	if (!room) return 0
	const storeRoom = rooms.find(candidate => String(candidate.id) === String(room.id)) || null
	const resolved = storeRoom || room
	let count = numericCount(resolved.users)
	if (count == null) count = numericCount(room.users)
	if (count == null) count = 0

	if (usesParticipantOccupancy(room) || usesParticipantOccupancy(resolved)) {
		return count
	}

	const isCurrentActiveRoom = (
		(activeRoomId != null && String(activeRoomId) === String(room.id)) ||
		(routeRoomId != null && String(routeRoomId) === String(room.id))
	)
	if (!isCurrentActiveRoom) return count

	if (Array.isArray(roomViewers)) {
		count = Math.max(count, roomViewers.length)
	}
	return Math.max(count, 1)
}

export function isRoomTypeAvailable(typeId, hasPermission, isAdminMode = false) {
	if (typeId === 'stage') {
		return hasPermission('world:rooms.create.stage') || isAdminMode
	}
	if (typeId === 'channel-bbb' || typeId === 'channel-janus' || typeId === 'channel-zoom') {
		return hasPermission('world:rooms.create.bbb') || isAdminMode
	}
	if (typeId === 'channel-jitsi') {
		return hasPermission('world:rooms.create.jitsi') || isAdminMode
	}
	if (typeId === 'channel-text') {
		return hasPermission('world:rooms.create.chat') || isAdminMode
	}
	if (typeId === 'channel-roulette') {
		return hasPermission('room:update') || isAdminMode
	}
	if (typeId === 'page-landing') {
		return hasPermission('room:update') || isAdminMode
	}
	return true
}

export function filterRoomTypesByPermission(roomTypes, hasPermission, isAdminMode = false) {
	return roomTypes.filter(type => isRoomTypeAvailable(type.id, hasPermission, isAdminMode))
}

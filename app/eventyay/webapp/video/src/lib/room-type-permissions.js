const TYPE_TO_PROVIDER = {
	'channel-bbb': 'bbb',
	'channel-jitsi': 'jitsi',
	'channel-janus': 'janus',
	'channel-zoom': 'zoom',
	'channel-loungemesh': 'loungemesh',
}

export function isRoomTypeAvailable(typeId, hasPermission, isAdminMode = false, videoProvidersConfig = null) {
	if (videoProvidersConfig && TYPE_TO_PROVIDER[typeId]) {
		const provider = TYPE_TO_PROVIDER[typeId]
		const conf = videoProvidersConfig[provider]
		if (conf === false || (conf && typeof conf === 'object' && conf.organizer === false)) {
			return false
		}
	}
	if (typeId === 'stage') {
		return hasPermission('world:rooms.create.stage') || isAdminMode
	}
	if (typeId === 'channel-bbb' || typeId === 'channel-janus' || typeId === 'channel-zoom') {
		return hasPermission('world:rooms.create.bbb') || isAdminMode
	}
	if (typeId === 'channel-jitsi') {
		return hasPermission('world:rooms.create.jitsi') || isAdminMode
	}
	if (typeId === 'channel-loungemesh') {
		return hasPermission('world:rooms.create.loungemesh') || hasPermission('world:rooms.create.bbb') || isAdminMode
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

export function filterRoomTypesByPermission(roomTypes, hasPermission, isAdminMode = false, videoProvidersConfig = null) {
	return roomTypes.filter(type => isRoomTypeAvailable(type.id, hasPermission, isAdminMode, videoProvidersConfig))
}

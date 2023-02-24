import router from 'router'

function getSessionRoute (session) {
	// a room having modules is a good enough indicator for a native room
	if (this.isLive && session.room?.modules) {
		return {name: 'room', params: {roomId: session.room.id}}
	}
	return {name: 'schedule:talk', params: {talkId: session.id}}
}

export default {
	provide: {
		linkTarget: '_blank',
		generateSessionLinkUrl ({session}) {
			if (session.url) return session.url
			return router.resolve(getSessionRoute.call(this, session)).href
		},
		async onSessionLinkClick (event, session) {
			if (!session.url) {
				event.preventDefault()
				await router.push(getSessionRoute.call(this, session))
			}
		}
	}
}

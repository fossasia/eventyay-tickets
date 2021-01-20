// TODO handle mobile stuff

import { getIdenticonSvgUrl } from 'lib/identicon'

const loadSettings = function () {
	try {
		return JSON.parse(localStorage.notificationSettings)
	} catch (e) {}
}

const notificationsSupported = typeof Notification !== 'undefined' // false on mobile safari

export default {
	namespaced: true,
	state: {
		permission: notificationsSupported && Notification.permission,
		permissionPromptDismissed: !!localStorage.notificationPermissionPromptDismissed,
		askingPermission: false,
		settings: loadSettings() || {
			notify: true,
			playSounds: false
		},
		desktopNotifications: []
	},
	getters: {
		showNotificationPermissionPrompt (state) {
			return notificationsSupported && !state.permissionPromptDismissed && state.permission === 'default'
		},
		shouldNotify (state) {
			return state.permission === 'granted' && !!state.settings.notify
		}
	},
	mutations: {
	},
	actions: {
		// sets state from browser permission and localStorage
		// TODO prevent switching of settings at app load
		pollExternals ({state, dispatch}) {
			state.permission = notificationsSupported && Notification.permission
			state.permissionPromptDismissed = !!localStorage.notificationPermissionPromptDismissed
			const settings = loadSettings()
			if (settings) {
				state.settings = settings
			}
		},
		async askForPermission ({state, dispatch}) {
			if (!notificationsSupported) return
			state.askingPermission = true
			let permission
			// safari only has callback
			try {
				permission = await Notification.requestPermission()
			} catch {
				permission = await new Promise((resolve) => Notification.requestPermission(resolve))
			}
			state.permission = permission
			state.askingPermission = false
			dispatch('dismissPermissionPrompt')
		},
		dismissPermissionPrompt ({state}) {
			state.permissionPromptDismissed = true
			localStorage.notificationPermissionPromptDismissed = true
		},
		updateSettings ({state}, settings) {
			state.settings = Object.assign({}, state.settings, settings)
			localStorage.notificationSettings = JSON.stringify(state.settings)
		},
		createDesktopNotification ({state, getters}, {title, body, tag, avatar, icon, onClose, onClick}) {
			if (!getters.shouldNotify || document.hasFocus()) return // don't show desktop notification when we have focus
			if (avatar) {
				if (avatar.url) {
					icon = avatar.url
				} else if (avatar.identicon) {
					const canvas = document.createElement('canvas')
					canvas.height = 192
					canvas.width = 192
					const img = document.createElement('img')
					img.src = getIdenticonSvgUrl(avatar.identicon)
					const ctx = canvas.getContext('2d')
					// TODO use onload?
					ctx.drawImage(img, 0, 0, 192, 192)
					icon = canvas.toDataURL()
				}
			}
			// TODO set tag to handle multiple tabs
			const desktopNotification = new Notification(title ?? '', {body, icon, tag})
			if (state.settings.playSounds) {
				const audio = new Audio('/notify.wav')
				audio.play()
			}
			desktopNotification.onclose = () => {
				onClose?.(desktopNotification)
				const index = state.desktopNotifications.indexOf(desktopNotification)
				if (index) state.desktopNotifications.splice(index, 1)
			}
			desktopNotification.onclick = () => {
				window.focus()
				onClick?.(desktopNotification)
			}
			state.desktopNotifications.push(desktopNotification)
			return desktopNotification
		},
		closeDesktopNotifications ({state}, fn) {
			for (const desktopNotification of state.desktopNotifications) {
				if (fn(desktopNotification)) desktopNotification.close()
			}
			state.desktopNotifications = state.desktopNotifications.filter(n => !fn(n))
		},
		clearDesktopNotifications ({state}) {
			for (const desktopNotification of state.desktopNotifications) {
				desktopNotification.close()
			}
			state.desktopNotifications = []
		}
	}
}

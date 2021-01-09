// TODO handle mobile stuff

export default {
	namespaced: true,
	state: {
		permission: Notification.permission,
		permissionPromptDismissed: false,
		askingPermission: false,
		settings: {
			notify: true,
			playSounds: false
		},
		desktopNotifications: []
	},
	getters: {
		showNotificationPermissionPrompt (state) {
			return !state.permissionPromptDismissed && state.permission === 'default'
		},
		shouldNotify (state) {
			return state.permission === 'granted' && state.settings.notify
		}
	},
	mutations: {
	},
	actions: {
		// sets state from browser permission and localStorage
		pollExternals ({state, dispatch}) {
			state.permission = Notification.permission
			state.permissionPromptDismissed = !!localStorage.notificationPermissionPromptDismissed
			state.settings = JSON.parse(localStorage.notificationSettings || null) || {}
		},
		async askForPermission ({state, dispatch}) {
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
			state.settings = Object.assing({}, state.settings, settings)
			localStorage.notificationSettings = state.settings
		},
		clearDesktopNotifications ({state}) {
			state.desktopNotifications = []
		}
	}
}

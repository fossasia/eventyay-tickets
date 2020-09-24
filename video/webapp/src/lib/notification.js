export default function notification (title, text, close = null, click = null, img = '') {
	if (localStorage.desktopNotificationPermission !== 'true') return
	const audio = new Audio('/notify.wav')
	const desktopNotification = new Notification(title, {body: text, icon: img})
	if (localStorage.playDesktopNotificationSound === 'true') audio.play()
	if (close) desktopNotification.onclose = close
	if (click) desktopNotification.onclick = click
	return desktopNotification
}

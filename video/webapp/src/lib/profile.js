import i18n from 'i18n'

// Function to get the display name of a user
export function getUserName(user) {
	// Return a localized string if the user is deleted
	if (user.deleted) return i18n.t('User:label:deleted')

	// Return the display name if available, otherwise return the sender or a default string
	return user.profile?.display_name ?? user.sender ?? '(unknown user)'
}

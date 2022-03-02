<template lang="pug">
.c-notifications(:class="{'has-background-media': hasBackgroundMedia}")
	notification-permission-notification(v-if="showNotificationPermissionPrompt")
	contact-request-notification(v-for="contactRequest of openContactRequests", :contactRequest="contactRequest")
	announcement(v-for="announcement of visibleAnnouncements", :announcement="announcement")
</template>
<script>
// TODO
// - scrolling
import { mapGetters } from 'vuex'
import Announcement from './Announcement'
import ContactRequestNotification from './ContactRequestNotification'
import NotificationPermissionNotification from './NotificationPermissionNotification'

export default {
	components: { Announcement, ContactRequestNotification, NotificationPermissionNotification },
	props: {
		hasBackgroundMedia: Boolean
	},
	data () {
		return {
		}
	},
	computed: {
		...mapGetters('notifications', ['showNotificationPermissionPrompt']),
		...mapGetters('exhibition', ['openContactRequests']),
		...mapGetters('announcement', ['visibleAnnouncements'])
	},
	created () {},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {}
}
</script>
<style lang="stylus">
.c-notifications
	position: fixed
	top: 3px
	right: 4px
	display: flex
	flex-direction: column
	width: 320px
	z-index: 600
	&.has-background-media
		top: 3px + 480px
	.ui-notification
		card()
		display: flex
		flex-direction: column
		margin: 4px 0
		padding: 8px
		position: relative
		#btn-close
			icon-button-style(style: clear)
			position: absolute
			top: 4px
			right: 4px
</style>

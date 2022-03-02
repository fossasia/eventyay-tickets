<template lang="pug">
.c-announcement-notification.ui-notification
	bunt-icon-button#btn-close(@click="dismiss") close
	.title {{ $t('notifications/Announcment:title') }}
	.details {{ announcement.text }}
</template>
<script>
// TODO
// - show expiry progress bar?
export default {
	props: {
		announcement: Object
	},
	methods: {
		dismiss () {
			this.$store.dispatch('announcement/dismissAnnouncement', this.announcement)
		}
	}
}
</script>
<style lang="stylus">
.c-announcement-notification
	.title
		color: $clr-secondary-text-light
		margin: 0 0 8px 0
</style>

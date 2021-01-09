<template lang="pug">
.c-notification-permission-notification.ui-notification
	bunt-icon-button#btn-close(@click="$store.dispatch('notifications/dismissPermissionPrompt')") close
	h1 Desktop Notifications
	p {{ $t('notifications/ContactRequestNotification:prompt') }}
	.actions
		bunt-button#btn-enable-desktop-notifications(@click="$store.dispatch('notifications/askForPermission')") enable notifications
		bunt-button#btn-dismiss(@click="$store.dispatch('notifications/dismissPermissionPrompt')") not now
</template>
<script>
export default {
	components: {},
	data () {
		return {
		}
	},
	computed: {},
	created () {},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {}
}
</script>
<style lang="stylus">
.c-notification-permission-notification
	h1
		font-size: 20px
		font-weight: 500
		margin: 0
	.actions
		display: flex
		justify-content: space-between
	#btn-enable-desktop-notifications
		themed-button-primary()
	#btn-dismiss
		themed-button-secondary()
</style>

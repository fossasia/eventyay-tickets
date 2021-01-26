<template lang="pug">
.c-notification-permission-notification.ui-notification
	bunt-icon-button#btn-close(@click="$store.dispatch('notifications/dismissPermissionPrompt')") close
	h1 {{ $t('notifications/NotificationPermissionNotification:title') }}
	p {{ $t('notifications/NotificationPermissionNotification:prompt') }}
	.actions
		bunt-button#btn-enable-desktop-notifications(@click="$store.dispatch('notifications/askForPermission')") {{ $t('notifications/NotificationPermissionNotification:accept:label') }}
		bunt-button#btn-dismiss(@click="$store.dispatch('notifications/dismissPermissionPrompt')") {{ $t('notifications/NotificationPermissionNotification:decline:label') }}
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
		flex-wrap: wrap
	#btn-enable-desktop-notifications
		themed-button-primary()
	#btn-dismiss
		themed-button-secondary()
</style>

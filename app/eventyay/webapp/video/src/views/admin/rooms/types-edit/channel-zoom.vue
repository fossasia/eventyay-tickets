<template lang="pug">
.c-channel-zoom-settings
	base-channel-form(
		providerId="zoom",
		:title="$t('Zoom Video Channel')",
		:subtitle="$t('Host Zoom meetings and webinars seamlessly with native app and browser join.')",
		providerIcon="mdi-video",
		v-bind="$props"
	)
		bunt-input(
			v-model="module.config.meeting_number",
			:label="$t('Zoom Meeting ID or Invite Link')",
			:placeholder="$t('e.g. 123 456 7890 or https://zoom.us/j/1234567890?pwd=...')",
			name="meeting_number",
			@input="onMeetingInput"
		)
		.input-hint {{ $t('You can paste a full Zoom link (passcode will be extracted automatically) or an ID.') }}
		bunt-input(v-model="module.config.password", :label="$t('Passcode (optional)')", name="password")
		bunt-checkbox(v-model="module.config.disable_chat", :label="$t('Disable Zoom in-meeting chat')", name="zoom_disable_chat")
		details.advanced-sdk-settings
			summary {{ $t('Advanced: Meeting SDK Credentials (Optional)') }}
			p.sdk-note {{ $t('Leave blank to use the modern one-click Zoom App and Web Client launcher. Only configure Client ID & Secret if using in-page Meeting SDK embedding.') }}
			bunt-input(v-model="module.config.client_id", :label="$t('Client ID (SDK Key)')", name="zoom_client_id")
			bunt-input(v-model="module.config.client_secret", :label="$t('Client Secret (SDK Secret)')", name="zoom_client_secret")
</template>
<script>
import BaseChannelForm from './BaseChannelForm'
import mixin from './mixin'

export default {
	components: { BaseChannelForm },
	mixins: [mixin],
	computed: {
		module() {
			if (!this.modules['call.zoom']) {
				this.addModule('call.zoom', {
					meeting_number: '',
					password: '',
					disable_chat: false,
					client_id: '',
					client_secret: ''
				})
			}
			return this.modules['call.zoom']
		}
	},
	created() {
		if (this.module) {
			this.module.config = {
				meeting_number: '',
				password: '',
				disable_chat: false,
				client_id: '',
				client_secret: '',
				...this.module.config
			}
		}
	},
	methods: {
		onMeetingInput(val) {
			if (!val || typeof val !== 'string') return
			const trimmed = val.trim()
			if (trimmed.includes('zoom.us') || trimmed.includes('/')) {
				const idMatch = trimmed.match(/\/(?:j|w|wc|my)(?:\/join)?\/([0-9]+)/)
				if (idMatch && idMatch[1]) {
					this.module.config.meeting_number = idMatch[1]
				}
				const pwdMatch = trimmed.match(/[?&]pwd=([^&#]+)/)
				if (pwdMatch && pwdMatch[1] && !this.module.config.password) {
					this.module.config.password = decodeURIComponent(pwdMatch[1])
				}
			}
		}
	}
}
</script>
<style lang="stylus">
.c-channel-zoom-settings
	.input-hint
		font-size 12px
		color var(--clr-text-secondary, #94a3b8)
		margin-top -4px
		margin-bottom 12px
	.advanced-sdk-settings
		margin-top 16px
		padding 12px
		border 1px solid var(--clr-border, #334155)
		border-radius 6px
		summary
			cursor pointer
			font-weight 600
			font-size 13px
			color var(--clr-text-primary, #f8fafc)
		.sdk-note
			font-size 12px
			color var(--clr-text-secondary, #94a3b8)
			margin 8px 0 12px 0
</style>

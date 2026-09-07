<template lang="pug">
.c-channel-janus-settings
	base-channel-form(
		providerId="janus",
		:title="$t('Janus WebRTC Channel')",
		:subtitle="$t('Low-latency, peer-to-peer and SFU video conferencing powered by the Janus WebRTC Gateway.')",
		providerIcon="mdi-webrtc",
		v-bind="$props"
	)
		bunt-checkbox(v-model="module.config.waiting_room", :label="$t('Put new users in waiting room first (requires moderator admission)')", name="janus_waiting_room")
		bunt-checkbox(v-model="module.config.start_with_audio_muted", :label="$t('Auto-mute users on start')", name="janus_audio_muted")
		bunt-checkbox(v-model="module.config.start_with_video_muted", :label="$t('Start with video muted')", name="janus_video_muted")
		bunt-checkbox(v-model="module.config.disable_cam", :label="$t('Disable camera for non-moderators')", name="janus_disable_cam")
		bunt-checkbox(v-model="module.config.disable_chat", :label="$t('Disable chat for non-moderators')", name="janus_disable_chat")
		bunt-input(v-model="module.config.prefer_server", :label="$t('Prefer Server with ID / URL')", name="janus_prefer_server")
</template>
<script>
import BaseChannelForm from './BaseChannelForm'
import mixin from './mixin'

export default {
	components: { BaseChannelForm },
	mixins: [mixin],
	computed: {
		module() {
			return this.modules['call.janus']
		}
	},
	created() {
		this.module.config = {
			prefer_server: '',
			start_with_audio_muted: false,
			start_with_video_muted: false,
			waiting_room: false,
			disable_cam: false,
			disable_chat: false,
			...this.module.config
		}
	}
}
</script>
<style lang="stylus">
</style>

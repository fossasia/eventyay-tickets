<template lang="pug">
.c-channel-jitsi-settings
	base-channel-form(
		providerId="jitsi",
		:title="$t('Jitsi Meet Channel')",
		:subtitle="$t('Scalable, encrypted video conferencing powered by Jitsi Meet with JWT role-based access.')",
		providerIcon="mdi-video",
		v-bind="$props"
	)
		bunt-checkbox(v-model="module.config.waiting_room", :label="$t('Put new users in waiting room / lobby first')", name="jitsi_waiting_room")
		bunt-checkbox(v-model="module.config.start_with_audio_muted", :label="$t('Start with audio muted')", name="jitsi_audio_muted")
		bunt-checkbox(v-model="module.config.start_with_video_muted", :label="$t('Start with video muted')", name="jitsi_video_muted")
		bunt-checkbox(v-model="module.config.record", :label="$t('Allow recording')", name="jitsi_record")
		bunt-checkbox(v-model="module.config.livestreaming", :label="$t('Allow live streaming')", name="jitsi_livestreaming")
		bunt-checkbox(v-model="module.config.disable_cam", :label="$t('Disable camera for non-moderators')", name="jitsi_disable_cam")
		bunt-checkbox(v-model="module.config.disable_chat", :label="$t('Disable chat for non-moderators')", name="jitsi_disable_chat")
		bunt-checkbox(v-model="module.config.require_display_name", :label="$t('Require display name before joining')", name="jitsi_require_display_name")
		bunt-input(v-model="module.config.prefer_server", :label="$t('Preferred Jitsi server URL')", name="jitsi_prefer_server")
</template>
<script>
import BaseChannelForm from './BaseChannelForm'
import mixin from './mixin'

export default {
	components: { BaseChannelForm },
	mixins: [mixin],
	computed: {
		module() {
			return this.modules['call.jitsi']
		}
	},
	created() {
		this.module.config = {
			prefer_server: '',
			start_with_audio_muted: false,
			start_with_video_muted: false,
			waiting_room: false,
			record: false,
			livestreaming: false,
			disable_cam: false,
			disable_chat: false,
			require_display_name: false,
			...this.module.config
		}
		delete this.module.config.room_name
		delete this.module.config.domain
		delete this.module.config.jwt_enabled
		delete this.module.config.app_id
		delete this.module.config.key_id
		delete this.module.config.app_secret
	}
}
</script>
<style lang="stylus">
</style>

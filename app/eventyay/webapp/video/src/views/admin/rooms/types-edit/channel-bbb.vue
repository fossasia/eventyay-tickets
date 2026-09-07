<template lang="pug">
.c-channel-bbb-settings
	base-channel-form(
		providerId="bbb",
		:title="$t('BigBlueButton Video Channel')",
		:subtitle="$t('Real-time collaborative meetings with presentation sharing, breakout rooms, and moderation.')",
		providerIcon="mdi-school",
		v-bind="$props"
	)
		bunt-checkbox(name="record", v-model="module.config.record", :label="$t('Allow recording (needs to be set before first join)')")
		bunt-checkbox(name="hide-presentation", v-model="module.config.hide_presentation", :label="$t('Hide presentation when users join')")
		bunt-checkbox(name="waiting-room", v-model="module.config.waiting_room", :label="$t('Put new users in waiting room first (needs to be set before first join)')")
		bunt-checkbox(name="auto-microphone", v-model="module.config.auto_microphone", :label="$t('Auto-join users with microphone on (skip dialog asking how to join)')")
		bunt-checkbox(name="auto-camera", v-model="module.config.auto_camera", :label="$t('Auto-join users with camera on')")
		bunt-checkbox(name="bbb-mute-on-start", v-model="module.config.bbb_mute_on_start", :label="$t('Auto-mute users')")
		bunt-checkbox(name="bbb-disable-cam", v-model="module.config.bbb_disable_cam", :label="$t('Disable camera for non-moderators')")
		bunt-checkbox(name="bbb-disable-chat", v-model="module.config.bbb_disable_chat", :label="$t('Disable public chat for non-moderators')")
		bunt-input(name="voice-bridge", v-model="module.config.voice_bridge", :label="$t('Voice Bridge ID')")
		bunt-input(name="prefer-server", v-model="module.config.prefer_server", :label="$t('Prefer Server with ID')")
		upload-url-input(name="presentation", v-model="module.config.presentation", :label="$t('Initial presentation')")
</template>
<script>
import UploadUrlInput from 'components/UploadUrlInput'
import BaseChannelForm from './BaseChannelForm'
import mixin from './mixin'

export default {
	components: { UploadUrlInput, BaseChannelForm },
	mixins: [mixin],
	computed: {
		module() {
			return this.modules['call.bigbluebutton']
		}
	}
}
</script>
<style lang="stylus">
</style>

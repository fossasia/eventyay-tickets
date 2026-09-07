<template lang="pug">
.c-channel-loungemesh-settings
	base-channel-form(
		providerId="loungemesh",
		:title="$t('LoungeMesh Spatial Lounge')",
		:subtitle="$t('Spatial proximity networking and workshop lounge powered by LoungeMesh.')",
		providerIcon="mdi-account-group",
		v-bind="$props"
	)
		bunt-checkbox(name="enable_notes", v-model="module.config.enable_notes", :label="$t('Enable shared collaborative notes')")
		bunt-checkbox(name="enable_whiteboard", v-model="module.config.enable_whiteboard", :label="$t('Enable shared interactive whiteboard')")
		bunt-checkbox(name="enable_spatial_chat", v-model="module.config.enable_spatial_chat", :label="$t('Enable spatial chat')")
		bunt-input(name="prefer_server", v-model="module.config.prefer_server", :label="$t('Preferred LoungeMesh server URL or ID')")
</template>
<script>
import BaseChannelForm from './BaseChannelForm'
import mixin from './mixin'

export default {
	components: { BaseChannelForm },
	mixins: [mixin],
	computed: {
		module() {
			if (!this.modules['call.loungemesh']) {
				this.addModule('call.loungemesh', {
					prefer_server: '',
					enable_notes: true,
					enable_whiteboard: true,
					enable_spatial_chat: true
				})
			}
			return this.modules['call.loungemesh']
		}
	},
	created() {
		if (this.module) {
			this.module.config = {
				prefer_server: '',
				enable_notes: true,
				enable_whiteboard: true,
				enable_spatial_chat: true,
				...this.module.config
			}
		}
	}
}
</script>
<style lang="stylus">
</style>

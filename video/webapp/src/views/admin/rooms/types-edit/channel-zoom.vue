<template lang="pug">
.c-channel-zoom-settings
	bunt-input(v-model="module.config.meeting_number", label="Meeting ID", name="meeting_number")
	bunt-input(v-model="module.config.password", label="Password", name="password")
	bunt-checkbox(v-model="module.config.disable_chat", label="Disable chat", name="zoom_disable_chat")
</template>
<script>
import UploadUrlInput from 'components/UploadUrlInput'
import mixin from './mixin'

export default {
	components: { UploadUrlInput },
	mixins: [mixin],
	computed: {
		module () {
			return this.modules['call.zoom']
		}
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
</style>

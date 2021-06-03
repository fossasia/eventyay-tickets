<template lang="pug">
.c-channel-roulette-settings
	bunt-input(v-model="module.config.rematch_interval", label="Minimum time before the same persons meet again (minutes)", name="rematch_interval")
</template>
<script>
import mixin from './mixin'

export default {
	mixins: [mixin],
	computed: {
		module () {
			const m = this.modules['networking.roulette']
			if (!m.config) {
				m.config = {}
			}
			if (!m.config.rematch_interval) {
				m.config.rematch_interval = 1440
			}
			return m
		}
	}
}
</script>
<style lang="stylus">
</style>

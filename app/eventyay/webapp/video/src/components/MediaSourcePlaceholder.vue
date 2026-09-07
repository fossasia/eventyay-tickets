<template lang="pug">
.c-media-source-placeholder(v-resize-observer="onResize")
</template>
<script>
// LIMITATIONS:
// - ResizeObserver does not fire on pure position changes, so we rely on layout/resize
//   changes to refresh the placeholder rect.
export default {
	components: {},
	data() {
		return {
		}
	},
	computed: {},
	created() {},
	async mounted() {
		await this.$nextTick()
		this.onResize()
		this._rafId = requestAnimationFrame(this.pollRect)
	},
	beforeUnmount() {
		if (this._rafId) {
			cancelAnimationFrame(this._rafId)
		}
		this.$store.commit('reportMediaSourcePlaceholderRect', null)
	},
	methods: {
		onResize() {
			this.$store.commit(
				'reportMediaSourcePlaceholderRect',
				this.$el.getBoundingClientRect(),
			)
		},
		pollRect() {
			if (!this.$el) return
			const rect = this.$el.getBoundingClientRect()
			const old = this.$store.state.mediaSourcePlaceholderRect
			if (!old || rect.top !== old.top || rect.left !== old.left || rect.width !== old.width || rect.height !== old.height) {
				this.onResize()
			}
			this._rafId = requestAnimationFrame(this.pollRect)
		}
	}
}
</script>
<style lang="stylus">
</style>

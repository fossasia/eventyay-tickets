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
		window.addEventListener('scroll', this.onResize, { passive: true })
		window.addEventListener('resize', this.onResize, { passive: true })
	},
	beforeUnmount() {
		window.removeEventListener('scroll', this.onResize)
		window.removeEventListener('resize', this.onResize)
		this.$store.commit('reportMediaSourcePlaceholderRect', null)
	},
	methods: {
		onResize() {
			if (!this.$el) return
			this.$store.commit(
				'reportMediaSourcePlaceholderRect',
				this.$el.getBoundingClientRect(),
			)
		}
	}
}
</script>
<style lang="stylus">
</style>

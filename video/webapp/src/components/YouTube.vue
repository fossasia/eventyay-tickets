<template lang="pug">
.c-youtube(:class="[`size-${size}`]")
	iframe(:src="url", allow="autoplay; fullscreen", allowfullscreen)
</template>
<script>
export default {
	props: {
		room: {
			type: Object,
			required: true
		},
		module: {
			type: Object,
			required: true
		},
		size: {
			type: String, // 'normal', 'tiny'
			default: 'normal'
		},
	},
	data () {
		return {
			error: null
		}
	},
	computed: {
		url () {
			return `http://www.youtube.com/embed/${this.module.config.ytid}?autoplay=1&rel=0&showinfo=0`
		}
	},
}
</script>
<style lang="stylus">
.c-youtube
	flex: auto
	display: flex
	flex-direction: column
	min-height: 0
	height: 100%
	background-color: $clr-black
	position: relative
	overflow: hidden
	iframe
		flex: auto
		min-height: 0
		height: 100%	/* required by Safari */
	&.size-tiny
		height: 48px
		width: 86px // TODO total guesstimate
		pointer-events: none
</style>

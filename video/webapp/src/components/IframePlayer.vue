<template lang="pug">
.c-iframe-player(:class="[`size-${size}`]")
	iframe(:src="module.config.url", allow="autoplay; fullscreen", allowfullscreen)
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
	}
}
</script>
<style lang="stylus">
.c-iframe-player
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

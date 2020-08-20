<template lang="pug">
.c-iframe-page
	bunt-progress-circular(size="huge", :page="true", v-if="loading")
	iframe(:src="this.module.config.url", allow="camera; autoplay; microphone; fullscreen; display-capture", allowfullscreen, allowusermedia, @load="loaded")
</template>
<script>
export default {
	props: {
		module: {
			type: Object,
			required: true
		}
	},
	data () {
		return {
			url: null,
			loading: false,
		}
	},
	methods: {
		loaded () {
			this.loading = false
		}
	}
}
</script>
<style lang="stylus">
.c-iframe-page
	flex: auto
	height: auto  // 100% breaks safari
	display: flex
	flex-direction: column
	position: relative
	iframe
		height: 100%
		width: 100%
		position: absolute
		top: 0
		left: 0
		border: none
		flex: auto // because safari
</style>

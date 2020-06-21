<template lang="pug">
.c-iframe
	bunt-progress-circular(size="huge", :page="true")
	iframe(:src="this.module.config.url", allow="camera; autoplay; microphone; fullscreen; display-capture", allowfullscreen, allowusermedia)
</template>
<script>
import api from 'lib/api'
export default {
	props: {
		room: {
			type: Object,
			required: true
		},
		module: {
			type: Object,
			required: true
		}
	},
	data () {
		return {
			url: null,
		}
	},
}
</script>
<style lang="stylus">
.c-iframe
	flex: auto
	height: 100%
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

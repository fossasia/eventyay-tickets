<template lang="pug">
.c-iframe-page
	bunt-progress-circular(size="huge", :page="true", v-if="loading")
	iframe(:src="url", allow="camera; autoplay; microphone; fullscreen; display-capture", allowfullscreen, allowusermedia, @load="loaded")
</template>
<script>
import {mapState} from 'vuex'

export default {
	props: {
		module: {
			type: Object,
			required: true
		}
	},
	data () {
		return {
			loading: false,
		}
	},
	computed: {
		...mapState(['user']),

		url () {
			let url = this.module.config.url
			url = url.replace('{display_name}', encodeURIComponent(this.user.profile.display_name))
			url = url.replace('{id}', encodeURIComponent(this.user.id))
			return url
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

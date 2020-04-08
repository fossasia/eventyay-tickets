<template lang="pug">
.c-livestream
	.video-container(ref="videoContainer")
		video(ref="video", style="width:100%;height:100%", data-shaka-player, autoplay)
</template>
<script>
import shaka from 'shaka-player/dist/shaka-player.ui.js'
import 'shaka-player/dist/controls.css'
export default {
	props: {
		room: {
			type: Object,
			required: true
		}
	},
	components: {},
	data () {
		return {
		}
	},
	computed: {
		streamModule () {
			return this.room.modules.find(module => module.type === 'livestream.native')
		}
	},
	created () {},
	async mounted () {
		const player = new shaka.Player(this.$refs.video)
		this.player = player
		player.addEventListener('error', (error) => {
			console.error(error.detail)
		})
		this.playerUI = new shaka.ui.Overlay(player, this.$refs.videoContainer, this.$refs.video)
		try {
			console.log('starting stream', this.streamModule.config.hls_url)
			await player.load(this.streamModule.config.hls_url)
		} catch (error) {
			console.error('player failed to load', error)
		}
	},
	methods: {}
}
</script>
<style lang="stylus">
.c-livestream
	flex: auto
	display: flex
	flex-direction: column
	min-height: 0
	.video-container
		flex: auto
		min-height: 0
	.shaka-controls-button-panel > .material-icons
		font-size: 24px
</style>

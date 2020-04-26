<template lang="pug">
.c-livestream(:class="[`size-${size}`]")
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
		},
		module: {
			type: Object,
			required: true
		},
		size: {
			type: String, // 'normal', 'mini'
			default: 'normal'
		}
	},
	components: {},
	data () {
		return {
		}
	},
	computed: {
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
			console.log('starting stream', this.module.config.hls_url)
			await player.load(this.module.config.hls_url)
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
	background-color: $clr-black
	.video-container
		flex: auto
		min-height: 0
	.shaka-controls-button-panel > .material-icons
		font-size: 24px
	&.size-mini
		height: 128px
		width: 230px // TODO total guesstimate
</style>

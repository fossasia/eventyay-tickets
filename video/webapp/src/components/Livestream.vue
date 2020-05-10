<template lang="pug">
.c-livestream(:class="[`size-${size}`]")
	.mdi.mdi-close(v-if="size === 'mini'", @click="$emit('close')")
	.video-container(ref="videoContainer")
		video(ref="video", style="width:100%;height:100%", data-shaka-player, autoplay, @playing="playingVideo", @pause="pausingVideo")
	.offline(v-if="offline")
		.offline-message  Stream offline
</template>
<script>
import { mapState } from 'vuex'
import shaka from 'shaka-player/dist/shaka-player.ui.js'
import 'shaka-player/dist/controls.css'

const RETRY_INTERVAL = 5000

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
			playing: true,
			offline: false
		}
	},
	computed: {
		...mapState(['streamingRoom'])
	},
	created () {},
	async mounted () {
		if (this.streamingRoom !== this.room) {
			this.$refs.video.muted = true
		}
		const player = new shaka.Player(this.$refs.video)
		this.player = player
		player.addEventListener('error', (error) => {
			console.error(error.detail)
		})
		this.playerUI = new shaka.ui.Overlay(player, this.$refs.videoContainer, this.$refs.video)
		const load = async () => {
			if (this._isDestroyed) return
			try {
				console.log('starting stream', this.module.config.hls_url)
				await player.load(this.module.config.hls_url)
			} catch (error) {
				console.error('player failed to load', error)
				if (error.code < 2000) { // network errors
					this.offline = true
					setTimeout(load, RETRY_INTERVAL)
				}
				// TODO handle other errors https://shaka-player-demo.appspot.com/docs/api/shaka.util.Error.html
			}
		}
		await load()
	},
	beforeDestroy () {
		this.player.unload()
		this.player.destroy()
	},
	methods: {
		playingVideo () {
			this.playing = true
		},
		pausingVideo () {
			this.playing = false
		}
	}
}
</script>
<style lang="stylus">
.c-livestream
	flex: auto
	display: flex
	flex-direction: column
	min-height: 0
	background-color: $clr-black
	position: relative
	> .mdi
		color: $clr-primary-text-dark
		position: absolute
		top: 4px
		right: 4px
		z-index: 100
		cursor: pointer
		font-size: 18px
		opacity: 0
		transition: opacity .6s ease
	&:hover > .mdi
		opacity: 1
	.video-container
		flex: auto
		min-height: 0
	.shaka-controls-button-panel > .material-icons
		font-size: 24px
	&.size-mini
		height: 128px
		width: 230px // TODO total guesstimate
	.offline
		position: absolute
		left: 0
		top: 0
		width: 100%
		height: 100%
		display: flex
		justify-content: center
		align-items: center
		background-color: $clr-blue-grey-200
		z-index: 100
		.offline-message
			font-size: 36px
</style>

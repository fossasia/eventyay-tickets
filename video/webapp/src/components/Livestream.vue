<template lang="pug">
.c-livestream(:class="[`size-${size}`, {playing}]")
	.mdi.mdi-close(v-if="size === 'mini'", @click="$emit('close')")
	.video-container(ref="videocontainer")
		video(ref="video", style="width:100%;height:100%", autoplay, @playing="playingVideo", @pause="pausingVideo", @volumechange="onVolumechange")
		.controls(@click="toggleVideo")
			.big-button.mdi(:class="{'mdi-play': !playing, 'mdi-pause': playing}")
			bunt-progress-circular(v-if="buffering", size="huge")
			.bottom-controls(@click.stop="")
				bunt-icon-button(@click="toggleVolume") {{ muted || volume === 0 ? 'volume_off' : 'volume_high' }}
				input.volume-slider(type="range", step="any", min="0", max="1", aria-label="Volume", :value="volume", @input="onVolumeSlider", :style="{'--volume': volume}")
				bunt-icon-button(@click="toggleFullscreen") {{ fullscreen ? 'fullscreen-exit' : 'fullscreen' }}
	.offline(v-if="offline")
		.offline-message {{ $t('Livestream:offline-message:text') }}
</template>
<script>
import { mapState } from 'vuex'
import shaka from 'shaka-player/dist/shaka-player.compiled.js'

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
			buffering: true,
			offline: false,
			fullscreen: false,
			volume: 1,
			muted: false
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
		this.onVolumechange()

		player.addEventListener('error', (error) => {
			console.error(error.detail)
		})
		player.addEventListener('buffering', ({buffering}) => {
			this.buffering = buffering
		})
		document.addEventListener('fullscreenchange', this.onFullscreenchange)
		const load = async () => {
			if (this._isDestroyed) return
			try {
				console.log('starting stream', this.module.config.hls_url)
				await player.load(this.module.config.hls_url)
				this.offline = false
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
		document.removeEventListener('fullscreenchange', this.onFullscreenchange)
	},
	methods: {
		toggleVideo () {
			if (this.$refs.video.paused) {
				this.$refs.video.play()
			} else {
				this.$refs.video.pause()
			}
		},
		toggleFullscreen () {
			if (document.fullscreenElement) {
				document.exitFullscreen()
			} else {
				this.$refs.videocontainer.requestFullscreen()
			}
		},
		toggleVolume () {
			this.$refs.video.muted = !this.muted
		},
		onVolumeSlider (event) {
			this.$refs.video.volume = event.target.value
			this.volume = event.target.value
		},
		onVolumechange () {
			if (this.$refs.video.muted) {
				this.volume = 0
				this.muted = true
			} else {
				this.volume = this.$refs.video.volume
				this.muted = false
			}
		},
		onFullscreenchange () {
			this.fullscreen = !!document.fullscreenElement
		},
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
	height: 100%
	background-color: $clr-black
	position: relative
	overflow: hidden
	> .mdi
		color: $clr-primary-text-dark
		position: absolute
		top: 4px
		right: 4px
		z-index: 100
		cursor: pointer
		font-size: 18px
		opacity: 0
		transition: opacity .3s ease
	.video-container
		flex: auto
		min-height: 0
		height: 100%	/* required by Safari */
	.controls
		position: absolute
		top: 0
		left: 0
		right: 0
		bottom: 0
		opacity: 0
		transition: opacity .3s ease
		.bunt-progress-circular, .big-button
			position: absolute
			top: 50%
			left: 50%
			transform: translate(-50%, -50%)
			z-index: 500
			pointer-events: none
		.big-button
			cursor: pointer
			height: 15vh
			width: @height
			font-size: @height
			line-height: @height
			padding: 4vh
			background-color: $clr-secondary-text-dark
			color: $clr-primary-text-light
			border-radius: 50%
		.bottom-controls
			position: absolute
			bottom: 0
			width: 100%
			display: flex
			justify-content: flex-end
			align-items: center
			padding: 16px 16px
			box-sizing: border-box
			.bunt-icon-button
				color: $clr-primary-text-dark
				height: 42px
				width: @height
				.bunt-icon
					height: 42px
					font-size: 32px
					line-height: @height
			.volume-slider
				cursor: pointer
				width: 100px
				height: 4px
				background: linear-gradient(to right, $clr-primary-text-dark, calc(var(--volume) * 100%), $clr-disabled-text-dark calc(var(--volume) * 100%))
				border-radius: 2px
				appearance: none
				outline: none
				&::-webkit-slider-runnable-track
					appearance: none
				&::-moz-range-track
					appearance: none
				thumb()
					appearance: none
					background-color: $clr-white
					height: 12px
					width: 12px
					border-radius: 50%
				&::-webkit-slider-thumb
					thumb()
				&::-moz-range-thumb
					thumb()
	.shaka-controls-button-panel > .material-icons
		font-size: 24px
	&:hover, &:not(.playing)
		.controls
			opacity: 1
		.mdi
			opacity: 1
	&.size-mini
		height: 128px
		width: 230px // TODO total guesstimate
		.big-button
			height: 36px
			width: @height
			font-size: @height
			line-height: @height
			padding: 16px
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

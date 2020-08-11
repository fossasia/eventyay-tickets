<template lang="pug">
.c-livestream(:class="[`size-${size}`, {playing, buffering, automuted, muted}]")
	.video-container(ref="videocontainer")
		video(ref="video", style="width:100%;height:100%", @playing="playingVideo", @pause="pausingVideo", @volumechange="onVolumechange")
		.controls(@click="toggleVideo")
			.automuted-unmute(v-if="automuted")
				span.mdi.mdi-volume-off
				span {{ $t('Livestream:automuted-unmute:text') }}
			.big-button.mdi.mdi-play(v-if="!playing")
			bunt-progress-circular(v-if="buffering && !offline", size="huge")
			.bottom-controls(@click.stop="")
				bunt-icon-button(@click="toggleVideo") {{ playing ? 'pause' : 'play' }}
				.buffer
				bunt-icon-button(@click="toggleVolume") {{ muted || volume === 0 ? 'volume_off' : 'volume_high' }}
				input.volume-slider(type="range", step="any", min="0", max="1", aria-label="Volume", :value="volume", @input="onVolumeSlider", :style="{'--volume': volume}")
				bunt-icon-button(@click="toggleFullscreen") {{ fullscreen ? 'fullscreen-exit' : 'fullscreen' }}
	.offline(v-if="offline")
		img.offline-image(v-if="theme.streamOfflineImage", :src="theme.streamOfflineImage")
		.offline-message(v-else) {{ $t('Livestream:offline-message:text') }}
</template>
<script>
// TODOS
// show controls based on mouse move time
import { mapState } from 'vuex'
import Hls from 'hls.js'
import theme from 'theme'

const RETRY_INTERVAL = 5000
const HLS_CONFIG = {
	// never fall behind live edge
	liveBackBufferLength: 0,
	liveMaxLatencyDurationCount: 5,
	fragLoadingMaxRetry: Infinity,
	fragLoadingMaxRetryTimeout: 5000,
	levelLoadingMaxRetry: Infinity,
	levelLoadingMaxRetryTimeout: 5000,
	manifestLoadingMaxRetry: Infinity,
	manifestLoadingMaxRetryTimeout: 5000
}

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
		}
	},
	components: {},
	data () {
		return {
			theme,
			playing: true,
			buffering: true,
			offline: false,
			fullscreen: false,
			volume: 1,
			muted: false,
			automuted: false
		}
	},
	computed: {
		...mapState(['streamingRoom'])
	},
	watch: {
		'module.config.hls_url': 'initializePlayer'
	},
	mounted () {
		document.addEventListener('fullscreenchange', this.onFullscreenchange)
		this.initializePlayer()
	},
	beforeDestroy () {
		this.player?.destroy()
		document.removeEventListener('fullscreenchange', this.onFullscreenchange)
	},
	methods: {
		initializePlayer () {
			this.player?.destroy()
			this.buffering = true
			const video = this.$refs.video
			const start = async () => {
				this.offline = false
				this.buffering = false
				try {
					if (!this.playing) return
					await video.play()
				} catch (e) {
					video.muted = true
					this.automuted = true
					video.play()
				}
				this.onVolumechange()
			}
			if (Hls.isSupported()) {
				const player = new Hls(HLS_CONFIG)
				let started = false
				player.attachMedia(this.$refs.video)
				this.player = player
				const load = () => {
					player.loadSource(this.module.config.hls_url)
				}
				player.on(Hls.Events.MEDIA_ATTACHED, () => {
					load()
				})
				player.on(Hls.Events.MANIFEST_PARSED, async (event, data) => {
					start()
					started = true
				})

				player.on(Hls.Events.ERROR, (event, data) => {
					console.error(event, data)
					if (data.details === Hls.ErrorDetails.BUFFER_STALLED_ERROR) {
						this.buffering = true
					} else if ([Hls.ErrorDetails.MANIFEST_LOAD_ERROR, Hls.ErrorDetails.LEVEL_LOAD_ERROR].includes(data.details)) {
						if (!started) {
							this.offline = true
							setTimeout(load, RETRY_INTERVAL)
						}
					} else if (data.type === Hls.ErrorTypes.NETWORK_ERROR) {
						this.buffering = true
						setTimeout(() => player.startLoad(), 250)
					}
				})

				player.on(Hls.Events.FRAG_BUFFERED, () => {
					this.buffering = false
				})
			} else if (video.canPlayType('application/vnd.apple.mpegurl')) {
				video.src = this.module.config.hls_url
				// TODO probably explodes on re-init
				// TODO doesn't seem like the buffer ring gets hidden?
				video.addEventListener('loadedmetadata', function () {
					start()
				})
			}
		},
		toggleVideo () {
			if (this.automuted) {
				this.toggleVolume()
				if (!this.$refs.video.paused) return
			}
			if (this.$refs.video.paused) {
				this.$refs.video.play()
				// force live edge after unpausing
				this.$refs.video.currentTime = this.$refs.video.buffered.end(this.$refs.video.buffered.length - 1)
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
			this.automuted = false
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
		.automuted-unmute
			display: flex
			align-items: center
			cursor: pointer
			position: absolute
			left: 50%
			top: 64px
			transform: translateX(-50%)
			background-color: $clr-primary-text-light
			color: $clr-primary-text-dark
			padding: 16px 24px
			border-radius: 36px
			font-size: 24px
			font-weight: 600
			.mdi
				margin-right: 16px
				font-size: 32px
				line-height: 32px
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
			padding: 8px 16px
			box-sizing: border-box
			.buffer
				flex: auto
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
	&:hover, &:not(.playing), &.buffering, &.automuted, &.muted
		.controls
			opacity: 1
		.mdi
			opacity: 1
	&.size-tiny
		height: 48px
		width: 86px // TODO total guesstimate
		pointer-events: none
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
		.offline-image
			height: 100%
			width: 100%
			object-fit: contain
			background: black
</style>

<template lang="pug">
.c-livestream(:class="[`size-${size}`, {playing, buffering, seeking, automuted, muted}]", v-resize-observer="onResize")
	.video-container(ref="videocontainer")
		video(ref="video", style="width:100%;height:100%", @playing="playingVideo", @pause="pausingVideo", @volumechange="onVolumechange")
		.controls(@click="toggleVideo")
			.automuted-unmute(v-if="automuted")
				span.mdi.mdi-volume-off
				span {{ $t('Livestream:automuted-unmute:text') }}
			.big-button.mdi.mdi-play(v-if="!playing")
			bunt-progress-circular(v-if="(buffering || seeking) && !offline", size="huge")
			.bottom-controls(@click.stop="")
				.progress-hover(v-if="seekable", ref="progress", @pointerdown="onProgressPointerdown", @pointermove="onProgressPointermove", @pointerup="onProgressPointerup", @pointercancel="onProgressPointerup", :style="progressStyles.play")
					.progress
						.load-progress(v-for="load of progressStyles.load", :style="load")
						.play-progress
					.progress-indicator
					.time(:style="{'--hovered-progress': hoveredProgress}") {{ formatTime(hoveredTime) }}
				bunt-icon-button(@click="toggleVideo") {{ playing ? 'pause' : 'play' }}
				.live-indicator(v-if="isLive") live
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
import config from 'config'
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
	components: {},
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
		onlyLive: {
			type: Boolean,
			default: true
		}
	},
	data () {
		return {
			theme,
			isLive: null,
			playing: true,
			buffering: true,
			seeking: false,
			offline: false,
			fullscreen: false,
			volume: 1,
			muted: false,
			automuted: false,
			currentTime: 0,
			duration: 0,
			bufferedRanges: null,
			hoveredProgress: null
		}
	},
	computed: {
		...mapState(['streamingRoom']),
		seekable () {
			return this.isLive === false || config.seekableLiveStreams
		},
		progressStyles () {
			return {
				play: {
					'--play-progress': this.currentTime / this.duration
				},
				load: this.bufferedRanges?.map(range => ({
					'--load-start': range.start / this.duration,
					'--load-length': (range.end - range.start) / this.duration
				}))
			}
		},
		hoveredTime () {
			return this.hoveredProgress * this.duration
		},
	},
	watch: {
		'module.config.hls_url': 'initializePlayer'
	},
	mounted () {
		document.addEventListener('fullscreenchange', this.onFullscreenchange)
		/* loadedmetadata */
		this.$refs.video.addEventListener('durationchange', this.onDurationchange)
		this.$refs.video.addEventListener('progress', this.onProgress)
		this.$refs.video.addEventListener('timeupdate', this.onTimeupdate)
		this.$refs.video.addEventListener('seeking', this.onSeeking)
		this.$refs.video.addEventListener('seeked', this.onSeeked)
		this.$refs.video.addEventListener('ended', this.onEnded)
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
				player.attachMedia(video)
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

				player.on(Hls.Events.LEVEL_LOADED, (event, data) => {
					this.isLive = data.details.live
					if (!data.details.live && this.onlyLive) {
						this.player?.destroy()
						this.offline = true
					}
				})

				player.on(Hls.Events.ERROR, (event, data) => {
					console.error(event, data)
					if (data.details === Hls.ErrorDetails.BUFFER_STALLED_ERROR) {
						this.buffering = true
					} else if ([Hls.ErrorDetails.MANIFEST_LOAD_ERROR, Hls.ErrorDetails.LEVEL_LOAD_ERROR].includes(data.details)) {
						if (!started) {
							this.offline = true
							setTimeout(load, RETRY_INTERVAL)
						} else if (data.response.code === 404) {
							this.initializePlayer()
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
		onDurationchange () {
			this.duration = this.$refs.video.duration
		},
		onProgress () {
			this.bufferedRanges = []
			for (let i = 0; i < this.$refs.video.buffered.length; i++) {
				this.bufferedRanges.push({
					start: this.$refs.video.buffered.start(i),
					end: this.$refs.video.buffered.end(i)
				})
			}
		},
		onTimeupdate () {
			this.currentTime = this.$refs.video.currentTime
		},
		onSeeking () {
			this.seeking = true
		},
		onSeeked () {
			this.seeking = false
		},
		onEnded () {
			this.player?.destroy()
			this.offline = true
		},
		onFullscreenchange () {
			this.fullscreen = !!document.fullscreenElement
		},
		playingVideo () {
			this.playing = true
		},
		pausingVideo () {
			this.playing = false
		},
		onProgressPointerdown (event) {
			this.$refs.progress.setPointerCapture(event.pointerId)
			this.mouseSeeking = true
			this.$refs.video.currentTime = this.hoveredProgress * this.duration
			// TODO respect video.seekable?
			// TODO show pos to seek
		},
		onProgressPointermove (event) {
			const el = this.$refs.progress
			const rect = el.getBoundingClientRect() // TODO probably killing performance
			this.hoveredProgress = Math.min(Math.max(0, (event.clientX - (rect.x + 16)) / (rect.width - 32)), 1)
			if (this.mouseSeeking) {
				this.$refs.video.currentTime = this.hoveredProgress * this.duration
			}
		},
		onProgressPointerup (event) {
			this.mouseSeeking = false
			this.$refs.progress.releasePointerCapture(event.pointerId)
		},
		onResize (event) {
			this.totalWidth = event[event.length - 1].contentRect.width
		},
		formatTime (s) {
			let prefix = ''
			if (this.isLive) {
				s = Math.abs(s - this.duration)
				prefix = '-'
			}
			const seconds = Math.floor(s % 60)
			const minutes = Math.floor((s / 60) % 60)
			const hours = Math.floor(s / 60 / 60)
			if (hours) {
				return `${prefix}${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
			} else {
				return `${prefix}${minutes}:${String(seconds).padStart(2, '0')}`
			}
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
			color: $clr-primary-text-dark
			.progress-hover
				position: absolute
				bottom: 54px
				left: 0
				width: 100%
				height: 16px
				cursor: pointer
				.progress
					position: absolute
					bottom: 0
					left: 16px
					width: calc(100% - 32px)
					height: 5px
					background-color: rgba(255,255,255,.2)
					overflow: hidden
					transition: transform .2s ease
					transform: scaleY(.6)
					.load-progress
						position: absolute
						top: 0
						left: calc(100% * var(--load-start))
						width: calc(100% * var(--load-length))
						height: 100%
						background-color: rgba(255,255,255,.5)
					.play-progress
						position: absolute
						top: 0
						left: 0
						width: calc(100% * var(--play-progress))
						height: 100%
						background-color: var(--clr-primary)
				.progress-indicator
					position: absolute
					left: calc((100% - 32px) * var(--play-progress) + 16px - 6.5px)
					top: 6.5px
					width: 13px
					height: 13px
					border-radius: 50%
					background-color: var(--clr-primary)
					transition: transform .2s ease
					transform: scale(0, 0)
				.time
					width: 64px // TODO less lazy
					text-align: center
					position: absolute
					top: -16px
					left: calc(min(max(0px, (100% - 32px) * var(--hovered-progress) - 16px), 100% - 64px))
					font-size: 14px
					font-weight: 500
					text-shadow: 0 0 4px $clr-primary-text-light
					opacity: 0
					transition: opacity .2s ease
				&:hover
					.progress, .progress-indicator
						transform: none
					.time
						opacity: 1
			.live-indicator
				text-transform: uppercase
				display: flex
				align-items: center
				pointer-events: none
				margin-left: 4px
				&::before
					content: ''
					display: block
					height: 6px
					width: @height
					border-radius: 50%
					background-color: $clr-red
					margin-right: 4px
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
	&:hover, &:not(.playing), &.buffering, &.seeking, &.automuted, &.muted
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

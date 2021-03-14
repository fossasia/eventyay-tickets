<template lang="pug">
.c-roulette
	.call(v-if="server")
		janus-videoroom(:server="server", :token="token", :iceServers="iceServers", :sessionId="sessionId", :roomId="roomId", size="normal", :automute="false", :key="`janus-videoroom-${roomId}`", @hangup="stopCall")
	.status(v-else-if="loading && !callId") {{ $t('Roulette:waiting:text') }}
	.status(v-else-if="loading && callId") {{ $t('Roulette:connecting:text') }}
	.welcome(v-else)
		.status {{ $t('Roulette:instructions:text') }}
		.preview-video-wrapper
			video(ref="video", playsinline, autoplay, muted="muted")
			bunt-icon-button(@click="showDevicePrompt = true") cog
		.preview-sound
			.mdi.mdi-microphone
			.bar-container
				.bar(:style="'width: ' + soundBarWidth + '%'")
		.error(v-if="videoError") {{ videoError }}
	.next
		bunt-button.btn-next(@click="findNewCall", :disabled="!videoReady", :error-message="error", :loading="loading") {{ $t('Roulette:btn-start:label') }}
	transition(name="prompt")
		a-v-device-prompt(v-if="showDevicePrompt", @close="showDevicePrompt = false; startVideo()")

</template>
<script>
import AVDevicePrompt from 'components/AVDevicePrompt'
import JanusVideoroom from 'components/janus/JanusVideoroom'
import SoundMeter from 'lib/webrtc/soundmeter'
import {mapActions, mapMutations, mapState} from 'vuex'

export default {
	components: {AVDevicePrompt, JanusVideoroom},
	props: {
		room: {
			type: Object,
			required: true
		},
		module: {
			type: Object,
			required: true,
		},
	},
	data () {
		return {
			showDevicePrompt: false,
			videoError: null,
			videoReady: false,
			soundLevel: 0,
			soundMeter: null,
			soundMeterInterval: null,
			previewStream: null,
		}
	},
	computed: {
		...mapState(['connected']),
		...mapState('roulette', ['callId', 'server', 'iceServers', 'token', 'roomId', 'sessionId', 'loading', 'error']),

		soundBarWidth () {
			return Math.min(1, this.soundLevel * 10) * 100
		}
	},
	watch: {
		connected (value) {
			if (value) {
				// resubscribe
				this.$store.dispatch('roulette/reconnect')
			}
		},
		server (value) {
			if (!this.server && !this.callId && !this.loading) {
				this.startVideo()
			}
		}
	},
	mounted () {
		this.startVideo()
	},
	destroyed () {
		if (this.soundMeter) {
			this.soundMeter.context.close()
		}
		if (this.previewStream) {
			this.previewStream.getTracks().forEach((track) => track.stop())
		}
		if (this.soundMeterInterval) {
			window.clearInterval(this.soundMeterInterval)
		}
		this.stopRequesting()
		this.stopCall()
	},
	methods: {
		...mapMutations('roulette', ['setLoading']),
		...mapActions('roulette', ['startCall', 'stopCall', 'startRequesting', 'stopRequesting']),

		findNewCall () {
			if (this.previewStream) {
				this.previewStream.getTracks().forEach((track) => track.stop())
			}
			if (this.soundMeter) {
				this.soundMeter.context.close()
			}
			if (this.soundMeterInterval) {
				window.clearInterval(this.soundMeterInterval)
			}
			this.stopCall()
			this.startRequesting({room: this.room})
		},
		startVideo () {
			const constraints = {
				audio: {deviceId: localStorage.audioInput ? {exact: localStorage.audioInput} : undefined},
				video: {deviceId: localStorage.videoInput ? {exact: localStorage.videoInput} : undefined},
			}
			navigator.mediaDevices.getUserMedia(constraints).then((stream) => {
				this.stream = stream
				this.$refs.video.srcObject = stream
				this.$refs.video.muted = 'muted'
				this.videoReady = true
				this.videoError = null
				this.previewStream = stream

				const atracks = stream.getAudioTracks()
				if (atracks && atracks.length !== 0) {
					try {
						window.AudioContext = window.AudioContext || window.webkitAudioContext
						const actx = new AudioContext()
						this.soundMeter = new SoundMeter(actx)
						this.soundMeter.connectToSource(stream)
						this.soundMeterInterval = window.setInterval(() => {
							this.soundLevel = parseFloat(this.soundMeter.slow.toFixed(2))
						}, 200)
					} catch (e) {
						// do not fail visibly, it is a nice-to-have feature
					}
				}
			}).catch((err) => {
				if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
					this.videoError = this.$t('AVDevice:error:notfound')
				} else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
					this.videoError = this.$t('AVDevice:error:notreadable')
				} else if (err.name === 'OverconstrainedError' || err.name === 'ConstraintNotSatisfiedError') {
					localStorage.videoInput = ''
					localStorage.audioInput = ''
					this.startVideo()
				} else if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
					this.videoError = this.$t('AVDevice:error:notallowed')
				} else if (err.name === 'TypeError' || err.name === 'TypeError') {
					this.videoError = err.name
				}
			})
		},
	},
}
</script>
<style lang="stylus">
.c-roulette
	flex: 100% 0 0
	max-height: 100%
	height: auto // 100% breaks safari
	display: flex
	flex-direction: column
	align-items: center
	justify-content: center
	.call
		width: 100%
		flex: auto 1 1
		position: relative
		.c-janusvideoroom
			position: absolute
			left: 0
			top: 0
			width: 100%
			height: 100%
	.status
		text-align: center
		padding: 16px
		font-size: 24px
	.error
		text-align: center
		padding: 16px
		font-size: 24px
		color: $clr-danger
	.next
		padding: 16px
		flex-shrink: 1
		text-align: center
		.btn-next
			themed-button-primary(size: large)
		.btn-config
			margin: 10px auto
			themed-button-secondary
	.preview-sound
		margin: 10px auto 0
		width: 510px
		max-width: 90vw
		display: flex
		flex-direction: row
		align-items: center
		.mdi
			font-size: 32px
			margin-right: 8px
		.bar-container
			flex: auto 1 1
			background: $clr-grey-200
			height: 8px
			border-radius: 4px
			.bar
				background: var(--clr-primary)
				height: 8px
				border-radius: 4px
				transition: width .5s

	.preview-video-wrapper
		background: black
		width: 510px
		max-width: 90vw
		margin: auto
		height: 270px
		position: relative
		overflow: hidden
		border-radius: 5px

		.bunt-icon-button
			position: absolute
			bottom: 20px
			right: 20px
			background: white
		video
			max-height: 100%
			max-width: 100%
			height: 100%
			object-fit: contain
			width: 100%
			transform: rotateY(180deg)
</style>

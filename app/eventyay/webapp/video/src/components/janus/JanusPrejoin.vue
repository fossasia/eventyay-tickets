<template lang="pug">
.c-janus-prejoin
	.prejoin-container
		.prejoin-layout
			//- Left: Video preview & quick media controls
			.preview-card
				.video-preview-wrap
					video.preview-video(
						ref="previewVideo",
						autoplay,
						playsinline,
						muted,
						:class="{ 'is-hidden': !cameraOn || !hasCameraStream }"
					)
					.preview-avatar(v-if="!cameraOn || !hasCameraStream")
						.mdi.mdi-account-circle
						span.avatar-name {{ displayName }}
					.preview-overlay-badge(v-if="!cameraOn")
						.mdi.mdi-video-off
						span {{ $t('Camera is off') }}

				.preview-controls
					button.preview-ctrl-btn(
						type="button",
						:class="{ 'is-off': !micOn }",
						:title="micOn ? $t('Mute microphone') : $t('Unmute microphone')",
						@click="toggleMic",
						id="prejoin-mic-btn"
					)
						.mdi(:class="micOn ? 'mdi-microphone' : 'mdi-microphone-off'")
						.vu-meter(v-if="micOn")
							.vu-bar(v-for="i in 4", :key="i", :class="{ active: audioLevel * 4 >= i }")

					button.preview-ctrl-btn(
						type="button",
						:class="{ 'is-off': !cameraOn }",
						:title="cameraOn ? $t('Turn off camera') : $t('Turn on camera')",
						@click="toggleCamera",
						id="prejoin-cam-btn"
					)
						.mdi(:class="cameraOn ? 'mdi-video' : 'mdi-video-off'")

					button.preview-ctrl-btn.btn-settings(
						type="button",
						:class="{ 'is-active': showSettings }",
						:title="$t('Device settings')",
						@click="showSettings = !showSettings",
						id="prejoin-settings-btn"
					)
						.mdi.mdi-cog

			//- Right: Join details, settings, and join action
			.join-card
				.room-header
					.room-badge
						.mdi.mdi-video-box
					.room-meta
						h2.room-name(v-html="$emojify(roomName)")
						p.room-subtitle {{ $t('Ready to join?') }}

				//- Expandable Device Settings
				transition(name="expand")
					.device-settings-panel(v-if="showSettings")
						.settings-title
							.mdi.mdi-tune
							span {{ $t('Audio & Video Devices') }}
						.device-field
							label
								.mdi.mdi-microphone
								span {{ $t('Microphone') }}
							select.device-select(v-model="selectedAudioInput", @change="applyDevices", id="prejoin-audio-input")
								option(value="") {{ $t('Default microphone') }}
								option(v-for="(d, index) in audioInputs", :key="d.deviceId", :value="d.deviceId") {{ d.label || `${$t('Microphone')} ${index + 1}` }}
						.device-field
							label
								.mdi.mdi-camera
								span {{ $t('Camera') }}
							select.device-select(v-model="selectedVideoInput", @change="applyDevices", id="prejoin-video-input")
								option(value="") {{ $t('Default camera') }}
								option(v-for="(d, index) in videoInputs", :key="d.deviceId", :value="d.deviceId") {{ d.label || `${$t('Camera')} ${index + 1}` }}

				//- Join Options Checkboxes
				.join-options
					label.toggle-option
						input.sr-only(type="checkbox", v-model="micOn", @change="handleMicToggle", id="prejoin-mic-toggle")
						.checkbox-box(:class="{ checked: micOn }")
							.mdi.mdi-check(v-if="micOn")
						span {{ $t('Start with microphone on') }}

					label.toggle-option
						input.sr-only(type="checkbox", v-model="cameraOn", @change="handleCameraToggle", id="prejoin-cam-toggle")
						.checkbox-box(:class="{ checked: cameraOn }")
							.mdi.mdi-check(v-if="cameraOn")
						span {{ $t('Start with camera on') }}

				//- Join Actions
				.join-actions
					button.btn-join-primary(type="button", @click="join", :disabled="joining", id="prejoin-join-btn")
						bunt-progress-circular(v-if="joining", size="small")
						template(v-else)
							.mdi.mdi-door-open
							span {{ $t('Join Meeting') }}

					.permission-alert(v-if="permissionError")
						.mdi.mdi-alert-circle-outline
						span {{ permissionError }}
</template>

<script>
import { mapState } from 'vuex'
import SoundMeter from 'lib/webrtc/soundmeter'

export default {
	name: 'JanusPrejoin',
	props: {
		roomName: {
			type: String,
			default: 'Meeting Room',
		},
	},
	emits: ['join'],
	data() {
		return {
			micOn: localStorage.micMuted === 'false',
			cameraOn: localStorage.videoRequested !== 'false',
			showSettings: false,
			audioInputs: [],
			videoInputs: [],
			selectedAudioInput: '',
			selectedVideoInput: '',
			audioLevel: 0,
			hasCameraStream: false,
			permissionError: null,
			joining: false,
			localStream: null,
			audioContext: null,
			soundMeter: null,
			meterInterval: null,
		}
	},
	computed: {
		...mapState(['user']),
		displayName() {
			return (
				this.user?.profile?.display_name ||
				this.user?.profile?.name ||
				this.$t('You')
			)
		},
	},
	async mounted() {
		await this.initDevices()
		await this.startPreview()
	},
	beforeUnmount() {
		this.stopPreview()
	},
	methods: {
		async initDevices() {
			if (!navigator.mediaDevices?.enumerateDevices) return
			try {
				const devices = await navigator.mediaDevices.enumerateDevices()
				this.audioInputs = devices.filter((d) => d.kind === 'audioinput')
				this.videoInputs = devices.filter((d) => d.kind === 'videoinput')
			} catch (e) {
				console.warn('Could not enumerate media devices:', e)
			}
		},
		async startPreview() {
			this.permissionError = null
			const constraints = {}

			if (this.micOn) {
				constraints.audio = this.selectedAudioInput
					? { deviceId: { exact: this.selectedAudioInput } }
					: true
			}
			if (this.cameraOn) {
				constraints.video = this.selectedVideoInput
					? { deviceId: { exact: this.selectedVideoInput }, width: { ideal: 1280 }, height: { ideal: 720 } }
					: { width: { ideal: 1280 }, height: { ideal: 720 } }
			}

			if (!constraints.audio && !constraints.video) {
				this.stopStreamTracks()
				return
			}

			try {
				const stream = await navigator.mediaDevices.getUserMedia(constraints)
				this.stopStreamTracks()
				this.localStream = stream

				if (this.$refs.previewVideo && stream.getVideoTracks().length > 0) {
					this.$refs.previewVideo.srcObject = stream
					this.hasCameraStream = true
				} else {
					this.hasCameraStream = false
				}

				if (stream.getAudioTracks().length > 0) {
					this.startAudioMeter(stream)
				}
				await this.initDevices()
			} catch (err) {
				console.warn('getUserMedia error in prejoin:', err)
				if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
					this.permissionError = this.$t('Permission to access camera or microphone was denied. Please allow access in browser settings.')
				} else {
					this.permissionError = this.$t('Could not access camera or microphone.')
				}
				this.hasCameraStream = false
			}
		},
		startAudioMeter(stream) {
			this.stopAudioMeter()
			try {
				const AudioContext = window.AudioContext || window.webkitAudioContext
				if (!AudioContext) return
				this.audioContext = new AudioContext()
				this.soundMeter = new SoundMeter(this.audioContext)
				this.soundMeter.connectToSource(stream, (e) => {
					if (e) return
					this.meterInterval = setInterval(() => {
						if (this.soundMeter) {
							this.audioLevel = Math.min(1, Math.max(0, this.soundMeter.instant * 4))
						}
					}, 100)
				})
			} catch (e) {
				console.warn('Could not initialize sound meter:', e)
			}
		},
		stopAudioMeter() {
			if (this.meterInterval) {
				clearInterval(this.meterInterval)
				this.meterInterval = null
			}
			if (this.soundMeter) {
				try { this.soundMeter.stop() } catch (e) {}
				this.soundMeter = null
			}
			if (this.audioContext && this.audioContext.state !== 'closed') {
				try { this.audioContext.close() } catch (e) {}
				this.audioContext = null
			}
			this.audioLevel = 0
		},
		stopStreamTracks() {
			if (this.localStream) {
				this.localStream.getTracks().forEach((t) => t.stop())
				this.localStream = null
			}
			if (this.$refs.previewVideo) {
				this.$refs.previewVideo.srcObject = null
			}
			this.hasCameraStream = false
			this.stopAudioMeter()
		},
		stopPreview() {
			this.stopStreamTracks()
		},
		async toggleMic() {
			this.micOn = !this.micOn
			this.handleMicToggle()
		},
		async toggleCamera() {
			this.cameraOn = !this.cameraOn
			this.handleCameraToggle()
		},
		async handleMicToggle() {
			localStorage.micMuted = (!this.micOn).toString()
			await this.startPreview()
		},
		async handleCameraToggle() {
			localStorage.videoRequested = this.cameraOn.toString()
			await this.startPreview()
		},
		async applyDevices() {
			await this.startPreview()
		},
		join() {
			this.joining = true
			this.stopPreview()
			this.$emit('join', {
				micOn: this.micOn,
				cameraOn: this.cameraOn,
				audioDeviceId: this.selectedAudioInput || null,
				videoDeviceId: this.selectedVideoInput || null,
			})
		},
	},
}
</script>

<style lang="stylus">
.c-janus-prejoin
	flex: auto
	height: 100%
	width: 100%
	max-width: 100%
	display: flex
	align-items: center
	justify-content: center
	background: #f5f5f5
	padding: 24px
	box-sizing: border-box
	overflow-y: auto
	overflow-x: hidden

	.prejoin-container
		width: 100%
		max-width: 860px
		min-width: 0
		box-sizing: border-box

	.prejoin-layout
		display: grid
		grid-template-columns: 1.2fr 1fr
		gap: 24px
		align-items: center

		+below('m')
			grid-template-columns: 1fr
			gap: 16px

	.preview-card
		background: #ffffff
		border: 1px solid #e2e8f0
		border-radius: 12px
		overflow: hidden
		box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06)
		display: flex
		flex-direction: column

		.video-preview-wrap
			position: relative
			width: 100%
			aspect-ratio: 16 / 9
			background-color: #1e293b
			display: flex
			align-items: center
			justify-content: center
			overflow: hidden

			.preview-video
				width: 100%
				height: 100%
				object-fit: cover
				transform: scaleX(-1) // mirror selfie preview
				&.is-hidden
					display: none

			.preview-avatar
				display: flex
				flex-direction: column
				align-items: center
				justify-content: center
				gap: 10px
				color: #e2e8f0

				.mdi-account-circle
					font-size: 80px
					color: #94a3b8

				.avatar-name
					font-size: 16px
					font-weight: 600
					color: #ffffff

			.preview-overlay-badge
				position: absolute
				bottom: 12px
				left: 12px
				background: rgba(0, 0, 0, 0.65)
				backdrop-filter: blur(4px)
				padding: 4px 10px
				border-radius: 6px
				display: flex
				align-items: center
				gap: 6px
				color: #f1f5f9
				font-size: 12px

		.preview-controls
			display: flex
			align-items: center
			justify-content: center
			gap: 16px
			padding: 16px
			background: #ffffff
			border-top: 1px solid #e5e7eb

			.preview-ctrl-btn
				display: inline-flex
				align-items: center
				justify-content: center
				position: relative
				width: 44px
				height: 44px
				border-radius: 50%
				border: 1px solid #d1d5db
				background: #f8fafc
				color: #374151
				cursor: pointer
				transition: all 0.2s ease

				&:hover
					background: #e8f4fd
					border-color: #2185d0
					color: #2185d0

				.mdi
					font-size: 22px

				&.is-off
					background: #fee2e2
					border-color: #fca5a5
					color: #dc2626

				&.is-active
					background: #2185d0
					border-color: #2185d0
					color: #ffffff

				.vu-meter
					position: absolute
					bottom: -4px
					display: flex
					gap: 2px

					.vu-bar
						width: 4px
						height: 4px
						border-radius: 1px
						background-color: #94a3b8
						&.active
							background-color: #16a34a

	.join-card
		background: #ffffff
		border: 1px solid #e2e8f0
		border-radius: 12px
		padding: 28px 24px
		box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06)
		display: flex
		flex-direction: column
		gap: 20px

		.room-header
			display: flex
			align-items: center
			gap: 14px

			.room-badge
				display: flex
				align-items: center
				justify-content: center
				width: 48px
				height: 48px
				border-radius: 12px
				background: #e8f4fd
				color: #2185d0
				font-size: 28px
				flex-shrink: 0

			.room-meta
				.room-name
					font-size: 20px
					font-weight: 700
					color: #111827
					margin: 0 0 2px 0

				.room-subtitle
					font-size: 13px
					color: #6b7280
					margin: 0

		.device-settings-panel
			background: #f8fafc
			border: 1px solid #e2e8f0
			border-radius: 8px
			padding: 14px
			display: flex
			flex-direction: column
			gap: 10px

			.settings-title
				display: flex
				align-items: center
				gap: 6px
				font-size: 13px
				font-weight: 600
				color: #1f2937

			.device-field
				display: flex
				flex-direction: column
				gap: 4px

				label
					display: flex
					align-items: center
					gap: 6px
					font-size: 12px
					color: #4b5563

				.device-select
					background: #ffffff
					border: 1px solid #d1d5db
					color: #111827
					border-radius: 6px
					padding: 6px 10px
					font-size: 13px
					outline: none

					&:focus
						border-color: #2185d0

		.join-options
			display: flex
			flex-direction: column
			gap: 10px

			.toggle-option
				display: flex
				align-items: center
				gap: 10px
				font-size: 14px
				color: #374151
				cursor: pointer
				user-select: none

				.checkbox-box
					width: 18px
					height: 18px
					border-radius: 4px
					border: 1px solid #d1d5db
					background: #ffffff
					display: flex
					align-items: center
					justify-content: center
					transition: all 0.15s ease

					&.checked
						background: #2185d0
						border-color: #2185d0
						color: #ffffff

					.mdi
						font-size: 14px

		.join-actions
			display: flex
			flex-direction: column
			gap: 12px

			.btn-join-primary
				display: inline-flex
				align-items: center
				justify-content: center
				gap: 8px
				background: #2185d0
				color: #ffffff
				border: none
				border-radius: 8px
				height: 46px
				font-size: 15px
				font-weight: 600
				cursor: pointer
				transition: all 0.2s ease

				&:hover:not(:disabled)
					background: #1678c2
					box-shadow: 0 4px 12px rgba(33, 133, 208, 0.25)

				&:disabled
					opacity: 0.6
					cursor: not-allowed

				.mdi
					font-size: 20px

			.permission-alert
				display: flex
				align-items: center
				gap: 8px
				background: #fee2e2
				border: 1px solid #fca5a5
				color: #b91c1c
				padding: 10px 12px
				border-radius: 6px
				font-size: 12.5px
.in-room-manager
	.c-janus-prejoin
		padding: 12px
		.prejoin-container
			max-width: 100%
		.prejoin-layout
			grid-template-columns: 1fr
			gap: 12px
		.join-card .room-header
			display: none
</style>

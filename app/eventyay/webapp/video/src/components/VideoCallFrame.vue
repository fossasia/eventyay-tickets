<template lang="pug">
.c-video-call-frame(:class="[`size-${size}`, `provider-${providerId}`, { 'is-fullscreen': isFullscreen }]")
	//- Unified Header Bar (hidden in miniplayer mode)
	.call-chrome-header(v-if="size !== 'tiny'")
		.header-left
			span.call-icon
				i.mdi.mdi-video
			.room-name-wrapper(v-if="room && room.name")
				span.room-title(v-html="$emojify(room.name)")
			.room-name-wrapper(v-else-if="call")
				span.room-title {{ $t('Private call') }}
		.header-right
			.connection-status(:class="connectionStatus")
				span.status-dot
				span.status-label {{ statusLabel }}
			button.chrome-action-btn(
				type="button",
				:title="isFullscreen ? $t('Exit fullscreen') : $t('Fullscreen')",
				@click="toggleFullscreen"
			)
				i.mdi(:class="isFullscreen ? 'mdi-fullscreen-exit' : 'mdi-fullscreen'")
			button.chrome-action-btn.btn-hangup(
				type="button",
				:title="$t('Leave call')",
				@click="leaveCall"
			)
				i.mdi.mdi-phone-hangup
				span.leave-text {{ $t('Leave') }}

	//- Call Body Area (100% viewport in miniplayer mode)
	.call-viewport(ref="viewportEl")
		JanusCall(
			v-if="providerId === 'janus'",
			ref="providerComponent",
			:room="room",
			:module="module",
			:size="size",
			:background="background",
			@connected="onConnected",
			@hangup="onHangup",
			@error="onError"
		)
		JanusChannelCall(
			v-else-if="providerId === 'janus-channel'",
			ref="providerComponent",
			:call="call",
			:size="size",
			:background="background",
			@close="onHangup"
		)
		JitsiCallFrame(
			v-else-if="providerId === 'jitsi'",
			ref="providerComponent",
			:room="room",
			:module="module",
			:size="size",
			@connected="onConnected",
			@hangup="onHangup",
			@error="onError"
		)
		BBBCallFrame(
			v-else-if="providerId === 'bbb'",
			ref="providerComponent",
			:room="room",
			:module="module",
			:size="size",
			@connected="onConnected",
			@hangup="onHangup",
			@error="onError"
		)

	//- Google Meet Style Overlay Header Bar (shown only in miniplayer mode on hover)
	.gmeet-pip-topbar(v-if="size === 'tiny'")
		.pip-title-badge
			span.live-dot
			span.pip-room-name(v-if="room && room.name", v-html="$emojify(room.name)")
			span.pip-room-name(v-else-if="call") {{ $t('Private call') }}
			span.pip-room-name(v-else) {{ $t('Meeting') }}
		.pip-top-actions
			button.pip-icon-btn(
				type="button",
				:title="$t('Return to room')",
				@click="maximizeCall"
			)
				i.mdi.mdi-arrow-expand
			button.pip-icon-btn.btn-leave(
				type="button",
				:title="$t('Leave call')",
				@click="leaveCall"
			)
				i.mdi.mdi-close

	//- Google Meet Style Floating Bottom Control Pill (shown only in miniplayer mode on hover)
	.gmeet-pip-controls(v-if="size === 'tiny'")
		button.pip-ctrl-btn(
			type="button",
			:class="{ 'active-danger': isMicMuted }",
			:title="isMicMuted ? $t('Unmute microphone') : $t('Mute microphone')",
			@click="toggleMic"
		)
			i.mdi(:class="isMicMuted ? 'mdi-microphone-off' : 'mdi-microphone'")
		button.pip-ctrl-btn(
			type="button",
			:class="{ 'active-danger': isCameraOff }",
			:title="isCameraOff ? $t('Turn on camera') : $t('Turn off camera')",
			@click="toggleCamera"
		)
			i.mdi(:class="isCameraOff ? 'mdi-video-off' : 'mdi-video'")
		button.pip-ctrl-btn(
			type="button",
			:title="$t('Return to room')",
			@click="maximizeCall"
		)
			i.mdi.mdi-arrow-expand
		button.pip-ctrl-btn.btn-hangup(
			type="button",
			:title="$t('Leave call')",
			@click="leaveCall"
		)
			i.mdi.mdi-phone-hangup
</template>

<script>
import JanusCall from 'components/JanusCall'
import JanusChannelCall from 'components/JanusChannelCall'
import JitsiCallFrame from 'components/JitsiCallFrame'
import BBBCallFrame from 'components/BBBCallFrame'

export default {
	name: 'VideoCallFrame',
	components: {
		JanusCall,
		JanusChannelCall,
		JitsiCallFrame,
		BBBCallFrame
	},
	props: {
		room: {
			type: Object,
			required: false,
			default: null,
		},
		module: {
			type: Object,
			required: false,
			default: null,
		},
		call: {
			type: Object,
			required: false,
			default: null,
		},
		size: {
			type: String,
			default: 'normal'
		},
		background: {
			type: Boolean,
			default: false
		}
	},
	emits: ['close', 'hangup', 'leave'],
	data() {
		return {
			isFullscreen: false,
			connectionStatus: 'connecting', // 'connecting', 'connected', 'error'
			error: null,
			isMicMuted: false,
			isCameraOff: false,
		}
	},
	computed: {
		providerId() {
			if (this.call) return 'janus-channel'
			if (!this.module) return 'unknown'
			if (this.module.type === 'call.janus') return 'janus'
			if (this.module.type === 'call.jitsi') return 'jitsi'
			if (this.module.type === 'call.bigbluebutton') return 'bbb'
			return 'unknown'
		},
		statusLabel() {
			switch (this.connectionStatus) {
				case 'connected':
					return this.$t('Connected')
				case 'error':
					return this.$t('Disconnected')
				default:
					return this.$t('Connecting…')
			}
		}
	},
	mounted() {
		document.addEventListener('fullscreenchange', this.onFullscreenChange)
	},
	beforeUnmount() {
		document.removeEventListener('fullscreenchange', this.onFullscreenChange)
	},
	methods: {
		onConnected() {
			this.connectionStatus = 'connected'
		},
		onHangup() {
			this.$emit('leave', this.room)
			this.$emit('hangup')
			this.$emit('close')
			if (this.size !== 'tiny' && (this.$route.name === 'room' || this.$route.name === 'room:manage' || this.$route.params?.roomId)) {
				this.$router.push({ name: 'about' }).catch(() => {
					this.$router.push('/').catch(() => {})
				})
			}
		},
		onError(err) {
			this.connectionStatus = 'error'
			this.error = err
		},
		maximizeCall() {
			if (this.room?.id) {
				this.$router.push({ name: 'room', params: { roomId: this.room.id } }).catch(() => {})
			} else if (this.call?.channel) {
				this.$router.push({ name: 'channel', params: { channelId: this.call.channel } }).catch(() => {})
			}
		},
		toggleMic() {
			const comp = this.$refs.providerComponent
			if (comp?.toggleMic) {
				comp.toggleMic()
				this.isMicMuted = !this.isMicMuted
			} else if (comp?.jitsiApi) {
				comp.jitsiApi.executeCommand('toggleAudio')
				this.isMicMuted = !this.isMicMuted
			}
		},
		toggleCamera() {
			const comp = this.$refs.providerComponent
			if (comp?.toggleCamera) {
				comp.toggleCamera()
				this.isCameraOff = !this.isCameraOff
			} else if (comp?.jitsiApi) {
				comp.jitsiApi.executeCommand('toggleVideo')
				this.isCameraOff = !this.isCameraOff
			}
		},
		leaveCall() {
			try {
				if (this.$refs.providerComponent?.cleanupMedia) {
					this.$refs.providerComponent.cleanupMedia()
				}
				if (this.$refs.providerComponent?.hangup) {
					this.$refs.providerComponent.hangup()
				}
			} catch (e) {
				console.warn('Error during provider cleanup:', e)
			}
			this.onHangup()
		},
		async toggleFullscreen() {
			if (!document.fullscreenElement) {
				try {
					await this.$el.requestFullscreen()
					this.isFullscreen = true
				} catch (err) {
					console.warn('Could not enter fullscreen:', err)
				}
			} else {
				try {
					await document.exitFullscreen()
					this.isFullscreen = false
				} catch (err) {
					console.warn('Could not exit fullscreen:', err)
				}
			}
		},
		onFullscreenChange() {
			this.isFullscreen = Boolean(document.fullscreenElement)
		}
	}
}
</script>

<style lang="stylus">
.c-video-call-frame
	display: flex
	flex-direction: column
	width: 100%
	height: 100%
	position: relative
	overflow: hidden
	background: #111827

	.call-chrome-header
		display: flex
		align-items: center
		justify-content: space-between
		height: 48px
		padding: 0 16px
		background: #181c24
		border-bottom: 1px solid rgba(255, 255, 255, 0.08)
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2)
		z-index: 10
		flex-shrink: 0

		.header-left
			display: flex
			align-items: center
			gap: 12px
			overflow: hidden

			.call-icon
				display: inline-flex
				align-items: center
				justify-content: center
				width: 28px
				height: 28px
				border-radius: 6px
				background: rgba(33, 133, 208, 0.15)
				color: #55a4ff
				font-size: 17px
				flex-shrink: 0

			.room-name-wrapper
				display: flex
				align-items: center
				overflow: hidden

				.room-title
					color: #f3f4f6
					font-size: 14px
					font-weight: 600
					white-space: nowrap
					overflow: hidden
					text-overflow: ellipsis

		.header-right
			display: flex
			align-items: center
			gap: 10px
			flex-shrink: 0

			.connection-status
				display: inline-flex
				align-items: center
				gap: 6px
				font-size: 12px
				color: #9ca3af

				.status-dot
					width: 8px
					height: 8px
					border-radius: 50%
					background-color: #f59e0b

				&.connected
					color: #34d399
					.status-dot
						background-color: #34d399
						box-shadow: 0 0 6px rgba(52, 211, 153, 0.5)

				&.error
					color: #ef4444
					.status-dot
						background-color: #ef4444

			.chrome-action-btn
				display: inline-flex
				align-items: center
				justify-content: center
				gap: 6px
				background: rgba(255, 255, 255, 0.08)
				border: 1px solid rgba(255, 255, 255, 0.14)
				color: #e5e7eb
				padding: 5px 12px
				border-radius: 6px
				font-size: 13px
				font-weight: 500
				cursor: pointer
				transition: all 0.15s ease

				&:hover
					background: rgba(255, 255, 255, 0.15)
					border-color: rgba(255, 255, 255, 0.25)
					color: #ffffff

				&.btn-hangup
					background: #dc2626
					border-color: #b91c1c
					color: #ffffff
					font-weight: 600

					&:hover
						background: #b91c1c
						border-color: #991b1b
						color: #ffffff

	.call-viewport
		flex: auto
		height: 100%
		width: 100%
		display: flex
		position: relative
		overflow: hidden
		background-color: #111827

	&.size-tiny
		position: fixed
		bottom: 24px
		right: 24px
		width: 380px
		height: 236px
		border-radius: 16px
		box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255, 255, 255, 0.1)
		z-index: 9999
		overflow: hidden
		background-color: #202124
		transition: transform 0.2s ease, box-shadow 0.2s ease

		&:hover
			box-shadow: 0 24px 48px -8px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255, 255, 255, 0.15)
			.gmeet-pip-topbar, .gmeet-pip-controls
				opacity: 1
				pointer-events: auto

		.call-chrome-header
			display: none

		.call-viewport
			position: absolute
			inset: 0
			width: 100%
			height: 100%
			background: #202124
			overflow: hidden

		.gmeet-pip-topbar
			position: absolute
			top: 0
			left: 0
			right: 0
			height: 48px
			padding: 0 12px
			display: flex
			align-items: center
			justify-content: space-between
			background: linear-gradient(180deg, rgba(0, 0, 0, 0.75) 0%, rgba(0, 0, 0, 0) 100%)
			z-index: 25
			opacity: 0
			pointer-events: none
			transition: opacity 0.2s ease

			.pip-title-badge
				display: flex
				align-items: center
				gap: 6px
				max-width: 240px
				overflow: hidden

				.live-dot
					width: 7px
					height: 7px
					border-radius: 50%
					background-color: #34d399
					box-shadow: 0 0 6px rgba(52, 211, 153, 0.6)
					flex-shrink: 0

				.pip-room-name
					color: #f1f5f9
					font-size: 12px
					font-weight: 600
					white-space: nowrap
					overflow: hidden
					text-overflow: ellipsis
					text-shadow: 0 1px 2px rgba(0, 0, 0, 0.8)

			.pip-top-actions
				display: flex
				align-items: center
				gap: 6px

				.pip-icon-btn
					background: rgba(30, 41, 59, 0.7)
					backdrop-filter: blur(8px)
					border: 1px solid rgba(255, 255, 255, 0.15)
					border-radius: 50%
					width: 28px
					height: 28px
					display: inline-flex
					align-items: center
					justify-content: center
					color: #f1f5f9
					cursor: pointer
					font-size: 15px
					transition: all 0.15s ease

					&:hover
						background: rgba(51, 65, 85, 0.9)
						color: #ffffff
						transform: scale(1.08)

		.gmeet-pip-controls
			position: absolute
			bottom: 12px
			left: 50%
			transform: translateX(-50%)
			display: flex
			align-items: center
			gap: 8px
			padding: 6px 10px
			background: rgba(32, 33, 36, 0.88)
			backdrop-filter: blur(12px)
			border-radius: 32px
			border: 1px solid rgba(255, 255, 255, 0.15)
			box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4)
			z-index: 25
			opacity: 0
			pointer-events: none
			transition: opacity 0.2s ease, transform 0.2s ease

			.pip-ctrl-btn
				background: rgba(60, 64, 67, 0.85)
				border: none
				border-radius: 50%
				width: 34px
				height: 34px
				display: inline-flex
				align-items: center
				justify-content: center
				color: #ffffff
				cursor: pointer
				font-size: 16px
				transition: all 0.15s ease

				&:hover
					background: rgba(95, 99, 104, 0.95)
					transform: scale(1.08)

				&.active-danger
					background: #ea4335
					color: #ffffff

					&:hover
						background: #d93025

				&.btn-hangup
					background: #ea4335
					color: #ffffff
					width: 38px
					height: 38px

					&:hover
						background: #d93025
						transform: scale(1.1)
</style>

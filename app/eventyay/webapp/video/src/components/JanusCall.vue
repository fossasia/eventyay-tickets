<template lang="pug">
.c-januscall(:class="[`size-${size}`]")
	.error-banner(v-if="error")
		.mdi.mdi-alert-circle-outline
		span {{ $t('We could not connect to the video conference server, sorry.') }}

	// Pre-join screen
	janus-prejoin(
		v-else-if="!joined && !left && !requestingAdmission && !waitingForAdmission && !denied && !error",
		:roomName="room.name || $t('Meeting Room')",
		@join="onPrejoinComplete"
	)

	// Waiting room: Requesting access
	.call-status-screen(v-else-if="requestingAdmission && !joined && !error")
		.status-card
			.status-icon.spin
				.mdi.mdi-loading
			h2 {{ $t('Requesting access...') }}
			p {{ room.name || $t('Meeting Room') }}

	// Waiting room: Host admission pending
	.call-status-screen(v-else-if="waitingForAdmission && !joined && !error")
		.status-card
			.status-icon.waiting
				.mdi.mdi-account-clock
			h2 {{ $t('Waiting for host to admit you...') }}
			p {{ room.name || $t('Meeting Room') }}
			.status-actions
				button.btn-status-action(type="button", @click="cancelWaitingRoom")
					.mdi.mdi-close
					span {{ $t('Leave Waiting Room') }}

	// Admission Denied screen
	.call-status-screen(v-else-if="denied && !error")
		.status-card
			.status-icon.denied
				.mdi.mdi-account-cancel
			h2 {{ $t('The host declined your request to join') }}
			p {{ room.name || $t('Meeting Room') }}
			.status-actions
				button.btn-status-primary(type="button", @click="returnToPrejoin")
					.mdi.mdi-refresh
					span {{ $t('Try Again') }}
				button.btn-status-action(type="button", @click="$router.push('/')")
					.mdi.mdi-arrow-left
					span {{ $t('Back to event') }}

	// Left Room screen
	.call-status-screen(v-else-if="left && !error")
		.status-card
			.status-icon.left
				.mdi.mdi-phone-hangup
			h2 {{ leftMessage }}
			p {{ room.name || $t('Meeting Room') }}
			.status-actions
				button.btn-status-primary(type="button", @click="rejoinRoom")
					.mdi.mdi-phone
					span {{ $t('Rejoin Meeting') }}
				button.btn-status-action(type="button", @click="$router.push({ name: 'about' })")
					.mdi.mdi-arrow-left
					span {{ $t('Back to event') }}

	// Live call
	janus-videoroom(
		v-else-if="joined && server",
		ref="videoroom",
		:server="server",
		:token="token",
		:iceServers="iceServers",
		:sessionId="sessionId",
		:audioSessionId="audioSessionId",
		:videoSessionId="videoSessionId",
		:screenShareSessionId="screenShareSessionId",
		:roomId="roomId",
		:eventRoomId="room.id",
		:room="room",
		:is-moderator="isModerator",
		:size="size",
		:automute="joinedWithMicMuted",
		:autovideo="!joinedWithCameraOff",
		@hangup="onRoomLeft"
	)
</template>

<script>
import api from 'lib/api'
import JanusVideoroom from 'components/janus/JanusVideoroom'
import JanusPrejoin from 'components/janus/JanusPrejoin'

export default {
	name: 'JanusCall',
	components: { JanusVideoroom, JanusPrejoin },
	props: {
		room: {
			type: Object,
			required: true,
		},
		module: {
			type: Object,
			required: true,
		},
		size: {
			type: String, // 'normal', 'tiny'
			default: 'normal',
		},
		background: Boolean,
	},
	emits: ['connected', 'hangup', 'error'],
	data() {
		return {
			server: null,
			token: null,
			iceServers: [],
			roomId: null,
			sessionId: null,
			audioSessionId: null,
			videoSessionId: null,
			screenShareSessionId: null,
			isModerator: false,
			loading: false,
			error: null,
			roomUrlPromise: null,
			// Lifecycle states
			joined: false,
			left: false,
			requestingAdmission: false,
			waitingForAdmission: false,
			denied: false,
			leftMessage: this.$t('You left the room'),
			joinedWithMicMuted: true,
			joinedWithCameraOff: false,
			apiMessageHandler: null,
		}
	},
	async created() {
		if (this.size === 'tiny' || this.background) {
			await this.fetchRoomUrl()
			if (this.server) this.joined = true
		} else if (!this.module.config?.waiting_room_enabled) {
			this.fetchRoomUrl()
		}
	},
	mounted() {
		this.apiMessageHandler = this.onApiMessage.bind(this)
		api.on('message', this.apiMessageHandler)
	},
	unmounted() {
		if (this.apiMessageHandler) {
			api.off('message', this.apiMessageHandler)
			this.apiMessageHandler = null
		}
	},
	methods: {
		onApiMessage(message) {
			const [name, payload] = message
			if (name !== 'januscall.admission_result') return
			if (String(payload?.room) !== String(this.room.id)) return
			if (payload.status === 'admitted' && payload.session) {
				this.applyRoomUrl(payload.session)
				this.waitingForAdmission = false
				this.denied = false
				this.left = false
				this.joined = true
			} else if (payload.status === 'denied') {
				this.clearRoomUrl()
				this.waitingForAdmission = false
				this.joined = false
				this.denied = true
			}
		},
		applyRoomUrl({ server, roomId, token, sessionId, audioSessionId, videoSessionId, screenShareSessionId, iceServers, isModerator }) {
			this.roomId = roomId
			this.token = token
			this.iceServers = iceServers
			this.sessionId = sessionId
			this.audioSessionId = audioSessionId
			this.videoSessionId = videoSessionId
			this.screenShareSessionId = screenShareSessionId
			this.isModerator = Boolean(isModerator)
			this.server = server
		},
		async fetchRoomUrl() {
			if (this.roomUrlPromise) return this.roomUrlPromise
			this.loading = true
			this.error = null
			this.roomUrlPromise = api.call('januscall.room_url', { room: this.room.id })
				.then((response) => {
					if (!this.$el || this._isDestroyed) return
					if (response.status === 'pending') {
						this.waitingForAdmission = true
						return
					}
					this.applyRoomUrl(response)
				})
				.catch((error) => {
					this.error = error
					this.loading = false
					this.$emit('error', error)
					console.error('Error fetching Janus room URL:', error)
				})
				.finally(() => {
					this.roomUrlPromise = null
				})
			return this.roomUrlPromise
		},
		async onPrejoinComplete(options = {}) {
			this.joinedWithMicMuted = !options.micOn
			this.joinedWithCameraOff = !options.cameraOn
			this.denied = false
			this.requestingAdmission = true
			if (!this.server) {
				await this.fetchRoomUrl()
			}
			this.requestingAdmission = false
			if (this.error) return
			if (this.waitingForAdmission) return
			this.joined = true
			this.$emit('connected')
		},
		async cancelWaitingRoom() {
			try {
				await api.call('januscall.waiting_room.cancel', { room: this.room.id })
			} catch (error) {
				console.warn('Error cancelling waiting room:', error)
			}
			this.waitingForAdmission = false
			this.requestingAdmission = false
			this.left = true
			this.leftMessage = this.$t('You left the waiting room')
			this.clearRoomUrl()
			this.$emit('hangup')
		},
		returnToPrejoin() {
			this.denied = false
			this.left = false
			this.leftMessage = this.$t('You left the room')
			this.clearRoomUrl()
		},
		onRoomLeft(payload = {}) {
			this.joined = false
			this.left = true
			this.requestingAdmission = false
			this.waitingForAdmission = false
			this.denied = false
			this.leftMessage = payload.message || this.$t('You left the room')
			this.clearRoomUrl()
			this.$emit('hangup')
		},
		rejoinRoom() {
			this.left = false
			this.leftMessage = this.$t('You left the room')
			this.fetchRoomUrl()
		},
		clearRoomUrl() {
			this.server = null
			this.token = null
			this.iceServers = []
			this.roomId = null
			this.sessionId = null
			this.audioSessionId = null
			this.videoSessionId = null
			this.screenShareSessionId = null
			this.isModerator = false
			this.requestingAdmission = false
			this.waitingForAdmission = false
		},
		toggleMic() {
			return this.$refs.videoroom?.toggleMic?.()
		},
		toggleCamera() {
			return this.$refs.videoroom?.toggleCamera?.()
		},
		cleanupMedia() {
			return this.$refs.videoroom?.hangup?.()
		},
		hangup() {
			return this.$refs.videoroom?.hangup?.()
		},
	},
}
</script>

<style lang="stylus">
.c-januscall
	flex: auto
	height: 100%
	width: 100%
	display: flex
	flex-direction: column
	position: relative
	overflow: hidden

	&.size-tiny
		height: 48px
		width: 86px
		pointer-events: none
		.controls, .mdi
			opacity: 0

	.error-banner
		display: flex
		align-items: center
		gap: 10px
		margin: 20px auto
		padding: 14px 20px
		background: #fee2e2
		border: 1px solid #fca5a5
		color: #b91c1c
		border-radius: 8px
		font-size: 14px

	.call-status-screen
		flex: auto
		display: flex
		align-items: center
		justify-content: center
		background: #f5f5f5
		padding: 24px
		box-sizing: border-box

		.status-card
			background: #ffffff
			border: 1px solid #e2e8f0
			border-radius: 12px
			box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06)
			padding: 36px 40px
			display: flex
			flex-direction: column
			align-items: center
			text-align: center
			gap: 16px
			max-width: 440px
			width: 100%

			h2
				font-size: 20px
				font-weight: 700
				color: #111827
				margin: 0

			p
				font-size: 14px
				color: #4b5563
				margin: 0

			.status-icon
				display: flex
				align-items: center
				justify-content: center
				width: 64px
				height: 64px
				border-radius: 50%
				font-size: 32px

				&.spin
					background: #e8f4fd
					color: #2185d0
					animation: spin 1s linear infinite

				&.waiting
					background: #fef3c7
					color: #d97706

				&.denied
					background: #fee2e2
					color: #dc2626

				&.left
					background: #f1f5f9
					color: #64748b

			.status-actions
				display: flex
				gap: 12px
				margin-top: 8px
				width: 100%
				justify-content: center

				button
					display: inline-flex
					align-items: center
					justify-content: center
					gap: 8px
					padding: 10px 18px
					border-radius: 8px
					font-size: 14px
					font-weight: 600
					cursor: pointer
					transition: all 0.2s ease

				.btn-status-primary
					background: #2185d0
					border: none
					color: #ffffff

					&:hover
						background: #1678c2
						transform: translateY(-1px)

				.btn-status-action
					background: #ffffff
					border: 1px solid #d1d5db
					color: #374151

					&:hover
						background: #f9fafb
						border-color: #2185d0
						color: #2185d0

@keyframes spin
	0%
		transform: rotate(0deg)
	100%
		transform: rotate(360deg)
</style>

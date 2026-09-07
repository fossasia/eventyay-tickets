<template lang="pug">
.c-bbb-call-frame(:class="[`size-${size}`]")
	.loading-state(v-if="loading")
		bunt-progress-circular(size="huge", :page="true")
		span.loading-text {{ $t('Joining meeting…') }}
	.error-state(v-else-if="error")
		.mdi.mdi-alert-circle-outline.state-icon--error
		p.error-title {{ $t('Could not join meeting room.') }}
		p.error-detail(v-if="errorMsg") {{ errorMsg }}
		bunt-button.retry-btn(@click="joinBBB") {{ $t('Retry') }}
	.bbb-viewport(v-show="!loading && !error && joinUrl")
		iframe.bbb-iframe(
			ref="iframeEl",
			:src="joinUrl",
			allow="camera *; microphone *; fullscreen *; display-capture *; autoplay *",
			allowfullscreen="true",
			allowusermedia="true",
			@load="onIframeLoaded"
		)
</template>

<script>
import api from 'lib/api'

export default {
	name: 'BBBCallFrame',
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
			type: String,
			default: 'normal'
		}
	},
	emits: ['connected', 'hangup', 'error'],
	data() {
		return {
			joinUrl: null,
			loading: true,
			error: null,
			errorMsg: null,
		}
	},
	async created() {
		await this.joinBBB()
	},
	mounted() {
		this.messageHandler = (event) => {
			if (event.data?.type === 'hangup' || event.data === 'hangup') {
				this.$emit('hangup')
			}
		}
		window.addEventListener('message', this.messageHandler)
	},
	beforeUnmount() {
		if (this.messageHandler) {
			window.removeEventListener('message', this.messageHandler)
		}
		this.cleanupMedia()
	},
	methods: {
		async joinBBB() {
			this.loading = true
			this.error = null
			this.errorMsg = null
			try {
				const response = await api.call('bbb.room_url', { room: this.room.id })
				if (response?.url) {
					this.joinUrl = response.url
					this.$emit('connected')
				} else {
					throw new Error('No join URL returned')
				}
			} catch (err) {
				this.loading = false
				this.error = err
				if (err?.code === 'bbb.join.missing_profile') {
					this.errorMsg = this.$t('Please update your display name in your profile to join.')
				} else {
					this.errorMsg = this.$t('Meeting server is currently unavailable.')
				}
				this.$emit('error', err)
			}
		},
		onIframeLoaded() {
			this.loading = false
		},
		cleanupMedia() {
			if (this.$refs.iframeEl) {
				try {
					this.$refs.iframeEl.src = 'about:blank'
				} catch (e) {}
			}
			this.joinUrl = null
		},
		hangup() {
			this.cleanupMedia()
			this.$emit('hangup')
		}
	}
}
</script>

<style lang="stylus">
.c-bbb-call-frame
	flex: auto
	height: 100%
	width: 100%
	display: flex
	flex-direction: column
	position: relative
	overflow: hidden
	background-color: #1e293b

	.loading-state, .error-state
		flex: auto
		display: flex
		flex-direction: column
		align-items: center
		justify-content: center
		color: #f1f5f9
		gap: 16px
		padding: 24px

		.loading-text
			font-size: 16px
			color: #94a3b8
			font-weight: 500

		.state-icon--error
			font-size: 48px
			color: #ef4444

		.error-title
			font-size: 18px
			font-weight: 600
			color: #f8fafc
			margin: 0

		.error-detail
			font-size: 14px
			color: #94a3b8
			margin: 0

		.retry-btn
			background-color: #2185d0
			color: #ffffff
			border-radius: 6px

	.bbb-viewport
		flex: auto
		width: 100%
		height: 100%
		position: relative
		overflow: hidden

		.bbb-iframe
			border: none
			width: 100%
			height: 100%
			display: block

	&.size-tiny
		.loading-state, .error-state
			display: none
</style>

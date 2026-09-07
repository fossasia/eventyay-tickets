<template lang="pug">
.c-jitsi-call-frame(:class="[`size-${size}`]")
	.loading-state(v-if="loading && !error")
		bunt-progress-circular(size="huge", :page="true")
		span.loading-text {{ $t('Connecting to meeting…') }}
	.error-state(v-else-if="error")
		.mdi.mdi-alert-circle-outline.state-icon--error
		p.error-title {{ $t('Could not join meeting room.') }}
		p.error-detail(v-if="errorMsg") {{ errorMsg }}
		bunt-button.retry-btn(@click="joinJitsi") {{ $t('Retry') }}
	.jitsi-container(ref="jitsiContainer", v-show="!error")
</template>

<script>
import api from 'lib/api'

export default {
	name: 'JitsiCallFrame',
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
	emits: ['connected', 'hangup', 'error', 'participants-change'],
	data() {
		return {
			loading: true,
			error: null,
			errorMsg: null,
			jitsiApi: null,
			isDestroyed: false,
			conferenceJoined: false,
			userHungUp: false
		}
	},
	async mounted() {
		await this.joinJitsi()
	},
	beforeUnmount() {
		this.isDestroyed = true
		this.cleanupMedia()
	},
	methods: {
		async joinJitsi() {
			this.loading = true
			this.error = null
			this.errorMsg = null
			this.conferenceJoined = false
			this.userHungUp = false
			this.cleanupMedia()
			await this.$nextTick()

			try {
				const config = await api.call('jitsi.room_config', { room: this.room.id })
				if (this.isDestroyed) return

				const isHttp = (config.protocol && config.protocol.startsWith('http:')) || (config.url && config.url.startsWith('http:'))
				const scheme = isHttp ? 'http' : 'https'
				const wsScheme = isHttp ? 'ws' : 'wss'
				const serverUrl = config.url || `${scheme}://${config.domain}`

				// Clean Eventyay meeting defaults
				const defaultToolbarButtons = [
					'camera', 'microphone', 'desktop', 'chat', 'raisehand',
					'participants-pane', 'tileview', 'select-background',
					'settings', 'fullscreen', 'videoquality', 'hangup'
				]
				const configOverwrite = {
					p2p: { enabled: false },
					enableLayerSuspension: true,
					resolution: 720,
					prejoinPageEnabled: false,
					prejoinConfig: { enabled: false },
					enableLobby: false,
					lobby: { enable: false },
					tokenAuthUrl: null,
					securityUi: { hideLobbyButton: true, disablePassword: true },
					requireDisplayName: false,
					disableDeepLinking: true,
					enableWelcomePage: false,
					welcomePage: { disabled: true },
					disableThirdPartyRequests: true,
					disableInviteFunctions: true,
					disablePolls: true,
					whiteboard: { enabled: false },
					toolbarConfig: { alwaysVisible: false, timeout: 4000 },
					toolbarButtons: config.configOverwrite?.toolbarButtons || defaultToolbarButtons,
					hideConferenceTimer: false,
					...(config.domain && !config.domain.includes('meet.jit.si') ? {
						bosh: `${scheme}://${config.domain}/http-bind`,
						websocket: `${wsScheme}://${config.domain}/xmpp-websocket`
					} : {}),
					...(config.configOverwrite || {})
				}

				if (!config.moderator) {
					configOverwrite.fileRecordingsEnabled = false
					configOverwrite.liveStreamingEnabled = false
					configOverwrite.disableRemoteMute = true
					configOverwrite.disableModeratorIndicator = true
					configOverwrite.securityUi = { hideLobbyButton: true, disablePassword: true }
					configOverwrite.remoteVideoMenu = { disableKick: true, disableGrantModerator: true, disablePrivateChat: false }
					configOverwrite.participantsPane = { hideModeratorSettingsTab: true, hideMoreActionsButton: true, hideMuteAllButton: true }
					configOverwrite.breakoutRooms = { hideAddRoomButton: true, hideAutoAssignButton: true, hideJoinRoomButton: true, hideModeratorSettingsTab: true, hideMoreActionsButton: true, hideMuteAllButton: true }
				}

				const interfaceConfigOverwrite = {
					APP_NAME: 'Eventyay Video',
					NATIVE_APP_NAME: 'Eventyay Video',
					PROVIDER_NAME: 'Eventyay',
					SHOW_JITSI_WATERMARK: false,
					SHOW_BRAND_WATERMARK: false,
					SHOW_POWERED_BY: false,
					SHOW_WATERMARK_FOR_GUESTS: false,
					SHOW_CHROME_EXTENSION_BANNER: false,
					SHOW_PROMOTIONAL_CLOSE_PAGE: false,
					HIDE_DEEP_LINKING_LOGO: true,
					GENERATE_ROOMNAMES_ON_WELCOME_PAGE: false,
					RECENT_LIST_ENABLED: false,
					TOOLBAR_ALWAYS_VISIBLE: false,
					DISABLE_VIDEO_BACKGROUND: true,
					DISABLE_JOIN_LEAVE_NOTIFICATIONS: false,
					...(config.interfaceConfigOverwrite || {})
				}

				const JitsiMeetExternalAPI = await this.loadJitsiExternalApi(config)
				if (this.isDestroyed) return

				await this.$nextTick()
				if (!this.$refs.jitsiContainer) {
					throw new Error('Jitsi container not available')
				}

				const safeUserInfo = {}
				if (config.userInfo?.displayName) {
					safeUserInfo.displayName = String(config.userInfo.displayName).trim()
				}
				if (config.userInfo?.email) {
					safeUserInfo.email = String(config.userInfo.email).trim()
				}
				if (config.userInfo?.avatar && typeof config.userInfo.avatar === 'string' && config.userInfo.avatar.trim() && !config.userInfo.avatar.includes('[object')) {
					safeUserInfo.avatarURL = config.userInfo.avatar.trim()
				}

				const jitsiOptions = {
					roomName: config.roomName,
					parentNode: this.$refs.jitsiContainer,
					serverURL: serverUrl,
					protocol: scheme,
					scheme: scheme,
					noSSL: (scheme === 'http'),
					configOverwrite,
					interfaceConfigOverwrite,
					userInfo: safeUserInfo
				}
				if (config.jwt) {
					jitsiOptions.jwt = config.jwt
				}

				this.jitsiApi = new JitsiMeetExternalAPI(config.domain, jitsiOptions)

				// Ensure iframe permissions are fully set
				this.$nextTick(() => {
					const iframe = this.$refs.jitsiContainer?.querySelector('iframe')
					if (iframe) {
						iframe.setAttribute('allow', 'camera *; microphone *; display-capture *; autoplay *; clipboard-write *; screen-wake-lock *; speaker-selection *')
						iframe.setAttribute('allowfullscreen', 'true')
						iframe.setAttribute('allowusermedia', 'true')
					}
				})

				// Once the iframe is mounted, reveal it immediately so the user can interact
				setTimeout(() => {
					if (!this.isDestroyed) {
						this.loading = false
						this.$emit('connected')
					}
				}, 400)

				this.jitsiApi.addListener('videoConferenceJoined', () => {
					this.loading = false
					this.conferenceJoined = true
					this.$emit('connected')
					if (config.roomDisplayName) {
						try {
							this.jitsiApi.executeCommand('subject', config.roomDisplayName)
						} catch (e) {}
					}
					if (!config.jwt && safeUserInfo.displayName) {
						try {
							this.jitsiApi.executeCommand('displayName', safeUserInfo.displayName)
						} catch (e) {}
					}
					if (!config.jwt && safeUserInfo.email) {
						try {
							this.jitsiApi.executeCommand('email', safeUserInfo.email)
						} catch (e) {}
					}
					if (safeUserInfo.avatarURL) {
						try {
							this.jitsiApi.executeCommand('avatarUrl', safeUserInfo.avatarURL)
						} catch (e) {}
					}
					try {
						this.jitsiApi.executeCommand('setTileView', true)
					} catch (e) {}
				})

				this.jitsiApi.addListener('videoConferenceLeft', () => {
					this.conferenceJoined = false
				})

				this.jitsiApi.addListener('readyToClose', () => {
					this.hangup()
				})

				this.jitsiApi.addListener('participantJoined', (p) => {
					this.$emit('participants-change', p)
				})

				this.jitsiApi.addListener('participantLeft', (p) => {
					this.$emit('participants-change', p)
				})
			} catch (err) {
				this.loading = false
				this.error = err
				if (err?.code === 'jitsi.join.missing_profile') {
					this.errorMsg = this.$t('Please update your display name in your profile to join.')
				} else if (err?.code === 'jitsi.server_unavailable') {
					this.errorMsg = this.$t('No active meeting server available.')
				} else {
					this.errorMsg = this.$t('Could not establish connection with meeting server.')
				}
				this.$emit('error', err)
			}
		},
		toggleMic() {
			if (this.jitsiApi) {
				this.jitsiApi.executeCommand('toggleAudio')
			}
		},
		toggleCamera() {
			if (this.jitsiApi) {
				this.jitsiApi.executeCommand('toggleVideo')
			}
		},
		cleanupMedia() {
			if (this.jitsiApi) {
				try {
					this.jitsiApi.dispose()
				} catch (e) {}
				this.jitsiApi = null
			}
			if (this.$refs.jitsiContainer) {
				this.$refs.jitsiContainer.innerHTML = ''
			}
		},
		hangup() {
			this.userHungUp = true
			if (this.jitsiApi) {
				try {
					this.jitsiApi.executeCommand('hangup')
				} catch (e) {}
			}
			this.cleanupMedia()
			this.$emit('hangup')
		},
		async loadJitsiExternalApi(config) {
			const patchExternalAPI = (api) => {
				if (api && api.prototype && !api._patchedForHttp) {
					const origCreateIFrame = api.prototype._createIFrame
					api.prototype._createIFrame = function(height, width, sandbox) {
						if (this._url && location.protocol === 'http:' && this._url.startsWith('https:')) {
							this._url = this._url.replace(/^https:/, 'http:')
						}
						return origCreateIFrame.call(this, height, width, sandbox)
					}
					api._patchedForHttp = true
				}
				return api
			}

			if (window.JitsiMeetExternalAPI) {
				return patchExternalAPI(window.JitsiMeetExternalAPI)
			}
			const baseUrl = config.url || (String(config.protocol).startsWith('http:') ? `http://${config.domain}` : `https://${config.domain}`)
			const scriptUrl = `${baseUrl.replace(/\/+$/, '')}/external_api.js`

			return new Promise((resolve, reject) => {
				const script = document.createElement('script')
				script.src = scriptUrl
				script.async = true
				script.onload = () => {
					if (window.JitsiMeetExternalAPI) {
						resolve(patchExternalAPI(window.JitsiMeetExternalAPI))
					} else {
						reject(new Error('JitsiMeetExternalAPI missing on window'))
					}
				}
				script.onerror = () => reject(new Error(`Failed to load script: ${scriptUrl}`))
				document.head.appendChild(script)
			})
		}
	}
}
</script>

<style lang="stylus">
.c-jitsi-call-frame
	flex: auto
	height: 100%
	width: 100%
	display: flex
	flex-direction: column
	position: relative
	overflow: hidden
	background-color: #111827

	.loading-state
		position: absolute
		inset: 0
		z-index: 10
		display: flex
		flex-direction: column
		align-items: center
		justify-content: center
		background-color: #111827
		color: #f1f5f9
		gap: 16px
		padding: 24px

		.loading-text
			font-size: 16px
			color: #94a3b8
			font-weight: 500

	.error-state
		flex: auto
		display: flex
		flex-direction: column
		align-items: center
		justify-content: center
		color: #f1f5f9
		gap: 16px
		padding: 24px

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

	.jitsi-container
		flex: auto
		width: 100%
		height: 100%
		position: relative

		iframe
			border: none
			width: 100%
			height: 100%
			display: block

	&.size-tiny
		.loading-state, .error-state
			display: none
</style>

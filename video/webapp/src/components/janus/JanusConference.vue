<template lang="pug">
.c-janusconference

	.connection-state(v-if="connectionState != 'connected'")
		div(v-if="connectionState == 'disconnected'") {{ $t('JanusVideoroom:disconnected:text') }}
		div.connection-error(v-else-if="connectionState == 'failed'")
			p {{ $t('JanusVideoroom:connection-error:text') }}
			p {{ connectionError }}
		bunt-progress-circular(v-else-if="connectionState == 'connecting'", size="huge", :page="true")

	audio(v-show="false", ref="mixedAudio", autoplay, playsinline)

	.participants(v-show="connectionState === 'connected'")
		.participant.me(:class="{talking: !knownMuteState && talkingParticipants.includes(ourAudioId)}", @click="showUserCard($event, user)")
			avatar(:user="user", :size="36")
			.mute-indicator(v-if="knownMuteState")
				.bunt-icon.mdi.mdi-microphone-off
		.participant(v-for="p in sortedParticipants", @click="showUserCard($event, p.venueless_user)", :class="{talking: !p.muted && talkingParticipants.includes(p.id)}")
			avatar(v-if="p.venueless_user", :user="p.venueless_user", :size="36")
			.mute-indicator(v-if="p.muted")
				.bunt-icon.mdi.mdi-microphone-off

	.users(v-show="connectionState === 'connected'", ref="container", :style="gridStyle", v-resize-observer="onResize")
		.me.feed(v-show="videoPublishingState !== 'unpublished'")
			.video-container(:style="{boxShadow: size != 'tiny' ? `0 0 0px 4px ${primaryColor.alpha(!knownMuteState && talkingParticipants.includes(ourAudioId) ? 255 : 0)}` : 'none'}")
				video(v-show="publishingWithVideo && videoPublishingState !== 'unpublished'", ref="ourVideo", autoplay, playsinline, muted="muted")
			.publishing-state(v-if="videoPublishingState !== 'published'")
				bunt-progress-circular(v-if="videoPublishingState == 'publishing'", size="huge", :page="true")
				div.publishing-error(v-else-if="videoPublishingState == 'failed'")
					p {{ $t('JanusVideoroom:publishing-error:text') }}
					p {{ publishingError }}
			.controls
				.user(@click="showUserCard($event, user)")
					avatar(:user="user", :size="36")
					span.display-name {{ user.profile.display_name }}
				bunt-icon-button(v-if="publishingWithVideo", @click="requestFullscreen($refs.ourVideo)") fullscreen
			.mute-indicator(v-if="knownMuteState")
				.bunt-icon.mdi.mdi-microphone-off

		.peer.feed(v-for="(f, idx) in sortedFeeds", :key="f.rfid", :style="{width: layout.width, height: layout.height}")
			.video-container(:style="{boxShadow: size != 'tiny' ? `0 0 0px 4px ${primaryColor.alpha(f.participant && !f.participant.muted && talkingParticipants.includes(f.rfid) ? 255 : 0)}` : 'none'}")
				video(v-show="f.rfattached", ref="peerVideo", autoplay, playsinline)
			.subscribing-state(v-if="!f.rfattached")
				bunt-progress-circular(size="huge", :page="true")
			.controls
				.user(v-if="f.venueless_user !== null", @click="showUserCard($event, f.venueless_user)")
					avatar(:user="f.venueless_user", :size="36")
					span.display-name {{ f.venueless_user.profile.display_name }}
				bunt-icon-button(v-if="f.rfattached", @click="requestFullscreen($refs.peerVideo[idx])") fullscreen
			.mute-indicator(v-if="f.participant && f.participant.muted")
				.bunt-icon.mdi.mdi-microphone-off

		.slow-banner(v-if="downstreamSlowLinkCount > 5 && (videoRequested || videoOutput)", @click="disableAllVideo") {{ $t('JanusConference:slow:text') }}

	.controlbar.controls(v-show="connectionState == 'connected'", :class="knownMuteState ? 'always' : ''")
		bunt-icon-button(@click="toggleVideo", :tooltip="videoRequested ? $t('JanusVideoroom:tool-video:off') : $t('JanusVideoroom:tool-video:on')") {{ !videoRequested ? 'video-off' : 'video' }}
		bunt-icon-button(@click="toggleMute", :tooltip="knownMuteState ? $t('JanusVideoroom:tool-mute:off') : $t('JanusVideoroom:tool-mute:on')") {{ knownMuteState ? 'microphone-off' : 'microphone' }}
		bunt-icon-button(@click="toggleScreenShare", :disabled="screensharingState === 'publishing' || screensharingState === 'unpublishing'", :tooltip="screensharingState == 'published' ? $t('JanusVideoroom:tool-screenshare:off') : $t('JanusVideoroom:tool-screenshare:on')") {{ screensharingState === 'published' ? 'monitor-off': 'monitor' }}
		bunt-icon-button(@click="showDevicePrompt = true", :tooltip="$t('JanusVideoroom:tool-settings:tooltip')") cog
		bunt-icon-button(@click="showFeedbackPrompt = true", :tooltip="$t('JanusVideoroom:tool-bug:tooltip')") message-alert-outline
		bunt-icon-button.hangup(@click="cleanup(); $emit('hangup')", :tooltip="$t('JanusVideoroom:tool-hangup:tooltip')") phone-hangup

	chat-user-card(v-if="selectedUser", ref="avatarCard", :sender="selectedUser", @close="selectedUser = null")
	transition(name="prompt")
		a-v-device-prompt(v-if="showDevicePrompt", @close="closeDevicePrompt")
		feedback-prompt(v-if="showFeedbackPrompt", module="janus", :collectTrace="collectTrace", @close="showFeedbackPrompt = false")
</template>
<script>
import {Janus} from 'janus-gateway'
import {mapState} from 'vuex'
import api from 'lib/api'
import ChatUserCard from 'components/ChatUserCard'
import Avatar from 'components/Avatar'
import AVDevicePrompt from 'components/AVDevicePrompt'
import FeedbackPrompt from 'components/FeedbackPrompt'
import {createPopper} from '@popperjs/core'
import Color from 'color'
import {colors} from 'theme'
import { v4 as uuid } from 'uuid'

const calculateLayout = (containerWidth, containerHeight, videoCount, aspectRatio, videoPadding) => {
	let bestLayout = {
		area: 0,
		cols: 0,
		rows: 0,
		width: 0,
		height: 0
	}

	// brute-force search layout where video occupy the largest area of the container
	for (let cols = 1; cols <= videoCount; cols++) {
		const rows = Math.ceil(videoCount / cols)
		const hScale = (containerWidth - cols * 2 * videoPadding) / (cols * aspectRatio)
		const vScale = (containerHeight - cols * 2 * videoPadding) / rows
		let width
		let height
		if (hScale <= vScale) {
			width = Math.floor((containerWidth - cols * 2 * videoPadding) / cols)
			height = Math.floor(width / aspectRatio)
		} else {
			height = Math.floor((containerHeight - cols * 2 * videoPadding) / rows)
			width = Math.floor(height * aspectRatio)
		}
		const area = width * height
		if (area > bestLayout.area) {
			bestLayout = {
				area,
				width,
				height,
				rows,
				cols
			}
		}
	}
	return bestLayout
}

const MIN_BITRATE = 64 * 1000
const MAX_BITRATE = 200 * 1000

const LOG_ENTRIES = []

const log = (source, level, message) => {
	LOG_ENTRIES.push([source, (new Date()).toISOString(), level, JSON.stringify(message)])
	console.log(`[${level}][${source}]`, message)
}

export default {
	components: {Avatar, AVDevicePrompt, ChatUserCard, FeedbackPrompt},
	props: {
		server: {
			type: String,
			required: true
		},
		token: {
			type: String,
			required: true
		},
		sessionId: {
			type: String,
			required: true
		},
		roomId: {
			type: String,
			required: true
		},
		iceServers: {
			type: Array,
			required: true
		},
		automute: {
			type: Boolean,
			default: false
		},
		size: {
			type: String, // 'normal', 'tiny'
			default: 'normal'
		},
	},
	data () {
		return {
			// State machines
			connectionState: 'disconnected', // disconnected, connecting, connected, failed
			audioReceivingState: 'pending', // pending, receiving
			videoReceivingState: 'pending', // pending, receiving, failed
			audioPublishingState: 'unpublished', // unpublished, publishing, published, failed
			videoPublishingState: 'unpublished', // unpublished, publishing, published, failed
			screensharingState: 'unpublished', // unpublished, publishing, published, unpublishing, failed

			// Error handling
			retryInterval: 1000,
			connectionError: null,
			connectionRetryTimeout: null,
			publishingError: null,
			screensharingError: null,

			// References to Janus.js
			janus: null,
			audioPluginHandle: null,
			videoPluginHandle: null,
			screensharePluginHandle: null,

			// Video controls state
			videoRequested: false,

			// Janus audiobridge state
			audioInput: null, // audio input currently requested from janus
			audioReceived: true, // janus *has* received our audio
			ourAudioId: null,
			participants: [],
			talkingParticipants: [],
			knownMuteState: this.automute,

			// Janus video call state
			videoPublishers: [],
			feeds: [],
			ourId: null,
			ourPrivateId: null,
			ourStream: null,
			ourScreenShareStream: null,
			publishingWithVideo: false, // we are *trying* to send video
			videoReceived: false, // janus *has* received our video
			videoInput: null, // video input currently requested from janus
			videoOutput: localStorage.videoOutput !== 'false',
			waitingForConsent: false,

			// Bandwidth control
			upstreamBitrate: MAX_BITRATE,
			upstreamSlowLinkCount: 0,
			downstreamSlowLinkCount: 0,

			// Layout utilities
			userCache: {},
			primaryColor: Color(colors.primary),
			showFeedbackPrompt: false,
			showDevicePrompt: false,
			selectedUser: null,
			layout: {
				area: 0,
				cols: 0,
				rows: 0,
				width: 0,
				height: 0
			},
		}
	},
	computed: {
		...mapState(['user']),

		sortedParticipants () {
			return this.participants.slice().sort((a, b) => a.venueless_user && b.venueless_user ? a.venueless_user.profile.display_name.localeCompare(b.venueless_user.profile.display_name) : 1)
		},
		sortedFeeds () {
			return this.feeds.slice().sort((a, b) => a.venueless_user && b.venueless_user ? a.venueless_user.profile.display_name.localeCompare(b.venueless_user.profile.display_name) : 1)
		},
		gridStyle () {
			return {
				'--video-width': `${this.layout.width}px`,
				'--video-height': `${this.layout.height}px`,
			}
		},
	},
	watch: {
		feeds () {
			this.onResize()
		},
		videoPublishingState () {
			this.onResize()
		}
	},
	destroyed () {
		if (this.janus) {
			this.cleanup()
		}
		if (this.connectionRetryTimeout) {
			window.clearTimeout(this.connectionRetryTimeout)
		}
	},
	mounted () {
		LOG_ENTRIES.splice(0, LOG_ENTRIES.length)
		if (this.janus) {
			this.cleanup()
		}
		this.initJanus()
		this.slowLinkInterval = window.setInterval(() => {
			this.downstreamSlowLinkCount = Math.max(this.downstreamSlowLinkCount - 1, 0)
			this.upstreamSlowLinkCount = Math.max(this.upstreamSlowLinkCount - 1, 0)
		}, 10000)
	},
	methods: {
		collectTrace () {
			// Yes, passing a function to a component is an antipattern in Vue, but I'm worried about the performance
			// penalty on Vue computing reactivity on our log which might get large.
			return LOG_ENTRIES
		},
		cleanup () {
			this.janus.destroy({cleanupHandles: true})
			this.connectionState = 'disconnected'
			this.audioReceivingState = 'pending'
			this.videoReceivingState = 'pending'
			this.audioPublishingState = 'unpublished'
			this.videoPublishingState = 'unpublished'
			this.screensharingState = 'unpublished'
			this.retryInterval = 1000
			this.connectionError = null
			this.screensharingError = null
			this.feeds = []
			this.participants = []
			this.ourStream = null
			this.ourScreenShareStream = null
		},
		onResize () {
			const bbox = this.$refs.container.getBoundingClientRect()
			this.layout = calculateLayout(
				this.size === 'tiny' ? bbox.width : bbox.width - 16 * 2,
				this.size === 'tiny' ? bbox.height : bbox.height - 16 * 2,
				this.feeds.length + (this.videoPublishingState !== 'unpublished' ? 1 : 0),
				16 / 9,
				this.size === 'tiny' ? 0 : 8,
			)
		},
		requestFullscreen (el) {
			el.parentElement.requestFullscreen()
		},
		closeDevicePrompt () {
			this.showDevicePrompt = false
			if (this.videoOutput !== (localStorage.videoOutput !== 'false')) {
				this.videoOutput = (localStorage.videoOutput !== 'false')
				if (this.videoOutput) {
					// Enable receiving video
					for (const f of this.videoPublishers) {
						if (!this.feeds.find(rf => rf.rfid === f.id)) {
							this.subscribeRemoteVideo(f.id, f.display, f.audio_codec, f.video_codec)
						}
					}
				} else {
					this.disableAllVideo()
				}
			} else {
				this.publishOwnVideo()
			}
			this.publishOwnAudio()
			if (typeof this.$refs.mixedAudio.setSinkId !== 'undefined') {
				this.$refs.mixedAudio.setSinkId(localStorage.audioOutput || '')
			}
		},
		async showUserCard (event, user) {
			this.selectedUser = user
			await this.$nextTick()
			const target = event.target.closest('.user, .participant')
			createPopper(target, this.$refs.avatarCard.$refs.card, {
				placement: 'bottom',
				modifiers: [{
					name: 'flip',
					options: {
						flipVariations: false
					}
				}]
			})
		},
		toggleScreenShare () {
			if (this.screensharingState === 'published') {
				this.screensharingState = 'unpublishing'
				this.screensharePluginHandle.send({message: {request: 'unpublish'}})
			} else if (this.screensharingState === 'unpublished') {
				if (this.screensharePluginHandle !== null) {
					this.publishOwnScreenshareFeed()
					return
				}
				this.janus.attach(
					{
						plugin: 'janus.plugin.videoroom',
						opaqueId: this.user.id,
						success: (pluginHandle) => {
							this.screensharePluginHandle = pluginHandle
							log('venueless', 'info',
								'Plugin attached! (' + this.screensharePluginHandle.getPlugin() + ', id=' + this.videoPluginHandle.getId() + ')')

							const register = {
								request: 'join',
								room: this.roomId,
								id: this.sessionId + ';screenshare;' + uuid(),
								ptype: 'publisher',
								token: this.token,
								display: 'new user'
							}
							this.screensharePluginHandle.send({message: register})
						},
						error: (error) => {
							log('venueless', 'error', '  -- Error attaching plugin...', error)
							alert('Screen sharing failed (error: ' + error.message + ')')
						},
						consentDialog: (on) => {
							this.waitingForConsent = on
						},
						iceState: (state) => {
							log('venueless', 'info', 'ICE state changed to ' + state)
							// if state "failed", show user, unless we're currently leaving the room
						},
						mediaState: (medium, on) => {
							log('venueless', 'info', 'Janus ' + (on ? 'started' : 'stopped') + ' receiving our ' + medium)
							if (medium === 'video' && on) {
								this.screensharingState = 'published'
							}
						},
						webrtcState: (on) => {
							log('venueless', 'info', 'Janus says our WebRTC PeerConnection is ' + (on ? 'up' : 'down') + ' now')
						},
						onmessage: (msg, jsep) => {
							log('venueless', 'debug', ' ::: Got a message (publisher) :::', msg)
							var event = msg.videoroom
							log('venueless', 'debug', 'Event: ' + event)
							if (event) {
								if (event === 'joined') {
									this.publishOwnScreenshareFeed(true)
								} else if (event === 'destroyed') {
									this.screensharingState = 'failed'
									this.screensharingError = 'The room has been destroyed.'
								} else if (event === 'event') {
									if (msg.unpublished) {
									// One of the publishers has unpublished?
										const unpublished = msg.unpublished
										log('venueless', 'info', 'Publisher left: ' + unpublished)
										if (unpublished === 'ok') {
											this.screensharingState = 'unpublished'
											this.screensharingError = null
											this.screensharePluginHandle.hangup()
											return
										}
									} else if (msg.error) {
										this.screensharingState = 'failed'
										if (msg.error_code === 426) {
											this.screensharingError = 'The room does not exist.'
										} else {
											this.screensharingError = msg.error
											alert('Screen sharing failed (error: ' + msg.error + ')')
										}
									}
								}
							}
							if (jsep) {
								log('venueless', 'debug', 'Handling SDP as well...', jsep)
								this.screensharePluginHandle.handleRemoteJsep({jsep: jsep})
								var audio = msg.audio_codec
								if (this.ourScreenShareStream && this.ourScreenShareStream.getAudioTracks() && this.ourScreenShareStream.getAudioTracks().length > 0 &&
									!audio) {
									// Audio has been rejected
									log('venueless', 'warning', 'Our audio stream has been rejected, viewers won\'t hear our screenshare')
								}
								var video = msg.video_codec
								if (this.ourScreenShareStream && this.ourScreenShareStream.getVideoTracks() && this.ourScreenShareStream.getVideoTracks().length > 0 &&
									!video) {
									this.screensharingState = 'failed'
									this.screensharingError = 'Stream rejected.'
								}
							}
						},
						onlocalstream: (stream) => {
							log('venueless', 'debug', ' ::: Got a local stream :::', stream)
							this.ourScreenShareStream = stream
							// todo: show local stream instead of remote Stream
						},
						slowLink: (uplink) => {
							log('venueless', 'info', 'slowlink on screenshare')
						},
						oncleanup: () => {
							log('venueless', 'info', ' ::: Got a cleanup notification: we are unpublished now :::')
							this.ourScreenShareStream = null
							this.screensharingState = 'unpublished'
						},
					})
			}
		},
		toggleVideo () {
			this.videoRequested = !this.videoRequested
			this.publishOwnVideo()
		},
		disableAllVideo () {
			this.videoRequested = false
			localStorage.videoRequested = false
			localStorage.videoOutput = false

			for (const h of this.feeds) {
				if (!h.rfid.includes(';screenshare;'))
					h.hangup()
			}

			this.videoOutput = (localStorage.videoOutput !== 'false')
			this.publishOwnVideo()
		},
		toggleMute () {
			if (this.audioPluginHandle == null) {
				return
			}
			this.knownMuteState = this.audioPluginHandle.isAudioMuted()
			if (this.knownMuteState) {
				this.audioPluginHandle.unmuteAudio()
				this.audioPluginHandle.send({message: { request: 'configure', muted: false }})
			} else {
				this.audioPluginHandle.muteAudio()
				this.audioPluginHandle.send({message: { request: 'configure', muted: true }})
			}
			this.knownMuteState = this.audioPluginHandle.isAudioMuted()
		},
		publishOwnVideo () {
			const media = {
				audioRecv: false,
				videoRecv: false,
				audioSend: false,
				videoSend: true,
			}

			if (this.videoRequested) {
				if (localStorage.videoInput) {
					media.video = {deviceId: localStorage.videoInput, width: 1280, height: 720}
				} else {
					media.video = 'hires'
				}
				if (localStorage.videoInput !== this.videoInput) {
					media.replaceVideo = true
					this.videoInput = localStorage.videoInput
				}
			} else {
				if (this.publishingWithVideo && this.videoPublishingState !== 'unpublished' && this.videoPublishingState !== 'failed') {
					this.videoPublishingState = 'unpublishing'
					const unpublish = {request: 'unpublish'}
					this.videoPluginHandle.send({message: unpublish})
				} else {
					this.videoPublishingState = 'unpublished'
				}
				return
			}

			this.publishingWithVideo = this.videoRequested
			if (this.videoRequested) {
				this.videoPublishingState = 'publishing'
			}

			this.videoPluginHandle.createOffer(
				{
					media: media,
					// If you want to test simulcasting (Chrome and Firefox only), set to true
					simulcast: false,
					simulcast2: false,
					success: (jsep) => {
						const publish = {request: 'configure', audio: true, video: this.publishingWithVideo, bitrate: this.upstreamBitrate}
						this.videoPluginHandle.send({message: publish, jsep: jsep})
					},
					error: (error) => {
						this.videoPublishingState = 'failed'
						this.publishingError = error.message
					},
				})
		},
		publishOwnAudio () {
			const media = {video: false}
			if (localStorage.audioInput) {
				media.audio = {deviceId: localStorage.audioInput}
			}
			if (localStorage.audioInput !== this.audioInput) {
				media.replaceAudio = true
				this.audioInput = localStorage.audioInput
			}
			this.audioPluginHandle.createOffer({
				media: media,
				success: (jsep) => {
					const publish = {request: 'configure', muted: this.knownMuteState}
					this.audioPluginHandle.send({message: publish, jsep: jsep})
				},
				error: (error) => {
					this.audioPublishingState = 'failed'
					this.publishingError = error.message
				},
			})
		},
		publishOwnScreenshareFeed () {
			// TODO: framerate? default of 3 is pretty low
			// TODO: currently, the "local" screenshare stream isn't handled specially, but also shown as a remote feed. This
			// should probably be changed, since this causes an echo when a tab is shared with audio
			const media = {audioRecv: false, videoRecv: false, audioSend: false, videoSend: true, video: 'screen', captureDesktopAudio: true}

			this.screensharingState = 'publishing'
			this.screensharePluginHandle.createOffer(
				{
					media: media,
					success: (jsep) => {
						log('venueless', 'debug', 'Got publisher SDP!', jsep)
						var publish = {request: 'configure', audio: true, video: true}
						this.screensharePluginHandle.send({message: publish, jsep: jsep})
					},
					error: (error) => {
						log('venueless', 'error', 'WebRTC error:', error)
						alert('Screen sharing failed (error: ' + error.message + ')')
						this.screensharingState = 'failed'
					},
				})
		},
		subscribeRemoteVideo (id, display, audio, video) {
			if (!this.videoOutput && !id.includes(';screenshare;')) {
				return
			}
			let remoteFeed = null
			this.janus.attach({
				plugin: 'janus.plugin.videoroom',
				opaqueId: this.user.id,
				success: (pluginHandle) => {
					remoteFeed = pluginHandle
					remoteFeed.simulcastStarted = false
					log('venueless', 'info', 'Plugin attached! (' + remoteFeed.getPlugin() + ', id=' + remoteFeed.getId() + ')')
					// We wait for the plugin to send us an offer
					var subscribe = {
						request: 'join',
						room: this.roomId,
						ptype: 'subscriber',
						feed: id,
						private_id: this.ourPrivateId,
					}
					// In case you don't want to receive audio, video or data, even if the
					// publisher is sending them, set the 'offer_audio', 'offer_video' or
					// 'offer_data' properties to false (they're true by default), e.g
					subscribe.offer_video = this.videoOutput || id.includes(';screenshare;')
					// For example, if the publisher is VP8 and this is Safari, let's avoid video
					if (Janus.webRTCAdapter.browserDetails.browser === 'safari' &&
						(video === 'vp9' || (video === 'vp8' && !Janus.safariVp8))) {
						if (video)
							video = video.toUpperCase()
						log('venueless', 'info', 'Publisher is using ' + video + ', but Safari doesn\'t support it: disabling video')
						subscribe.offer_video = false
					}
					remoteFeed.videoCodec = video
					remoteFeed.send({message: subscribe})
				},
				error: (error) => {
					log('venueless', 'error', '  -- Error attaching plugin...', error)
					alert('Error attaching plugin... ' + error)
				},
				onmessage: (msg, jsep) => {
					log('venueless', 'debug', ' ::: Got a message (subscriber) :::', msg)
					var event = msg.videoroom
					log('venueless', 'debug', 'Event: ' + event)
					if (msg.error) {
						log('venueless', 'error', 'Error when subscribing: ' + msg.error)
						// todo: show something?
					} else if (event) {
						if (event === 'attached') {
							// Subscriber created and attached
							remoteFeed.rfattached = false
							remoteFeed.hasVideo = true
							remoteFeed.rfid = msg.id
							remoteFeed.participant = this.participants.find(pp => pp.id === remoteFeed.rfid)
							remoteFeed.venueless_user = null
							this.feeds.push(remoteFeed)
							this.fetchUser(remoteFeed)
						} else if (event === 'event') {
							// Check if we got a simulcast-related event from this publisher
							var substream = msg.substream
							var temporal = msg.temporal
							if ((substream !== null && substream !== undefined) ||
								(temporal !== null && temporal !== undefined)) {
								if (!remoteFeed.simulcastStarted) {
									remoteFeed.simulcastStarted = true
									// Add some new buttons
									// addSimulcastButtons(remoteFeed.rfindex,
									//	remoteFeed.videoCodec === 'vp8' || remoteFeed.videoCodec === 'h264')
								}
								// We just received notice that there's been a switch, update the buttons
								// updateSimulcastButtons(remoteFeed.rfindex, substream, temporal)
							}
						} else {
							// What has just happened?
						}
					}
					if (jsep) {
						log('venueless', 'debug', 'Handling SDP as well...', jsep)
						// Answer and attach
						remoteFeed.createAnswer({
							jsep: jsep,
							// Add data:true here if you want to subscribe to datachannels as well
							// (obviously only works if the publisher offered them in the first place)
							media: {audioSend: false, videoSend: false},	// We want recvonly audio/video
							success: (jsep) => {
								log('venueless', 'debug', 'Got SDP!', jsep)
								var body = {request: 'start', room: this.roomId}
								remoteFeed.send({message: body, jsep: jsep})
							},
							error: (error) => {
								log('venueless', 'error', 'WebRTC error:', error)
								alert('WebRTC error... ' + error.message)
							},
						})
					}
				},
				iceState: (state) => {
					log('venueless', 'info',
						'ICE state of this WebRTC PeerConnection (feed #' + remoteFeed.rfid + ') changed to ' + state)
				},
				webrtcState: (on) => {
					log('venueless', 'info',
						'Janus says this WebRTC PeerConnection (feed #' + remoteFeed.rfid + ') is ' + (on ? 'up' : 'down') +
						' now')
				},
				slowLink: (uplink) => {
					log('venueless', 'info', 'slowLink on subscriber')
					this.downstreamSlowLinkCount++
				},
				onremotestream: (stream) => {
					log('venueless', 'debug', 'Remote feed #' + remoteFeed.rfid + ', stream:', stream)
					const rfindex = this.feeds.findIndex((rf) => rf.rfid === remoteFeed.rfid)
					const videoTracks = stream.getVideoTracks()

					remoteFeed.rfattached = true
					remoteFeed.hasVideo = videoTracks && videoTracks.length > 0
					this.$set(this.feeds, rfindex, remoteFeed) // force reactivity
					this.$nextTick(() => {
						Janus.attachMediaStream(this.$refs.peerVideo[rfindex], stream)
					})
				},
				oncleanup: () => {
					const idx = this.feeds.indexOf(remoteFeed)
					if (idx > -1) this.feeds.splice(idx, 1)
				}
			})
		},
		onJanusConnected () {
			// Roughly based on https://janus.conf.meetecho.com/audiobridgetest.js
			this.janus.attach(
				{
					plugin: 'janus.plugin.audiobridge',
					opaqueId: this.user.id,
					success: (pluginHandle) => {
						this.audioPluginHandle = pluginHandle
						log('venueless', 'info', 'Plugin attached! (' + this.audioPluginHandle.getPlugin() + ', id=' + this.audioPluginHandle.getId() + ')')

						const register = {
							request: 'join',
							room: this.roomId,
							token: this.token,
							id: this.sessionId,
							display: 'venueless user',
							muted: this.automute
						}
						this.knownMuteState = this.automute
						this.audioPluginHandle.send({message: register})
					},
					error: (error) => {
						this.connectionState = 'failed'
						this.connectionError = error
						this.cleanup()
						window.setTimeout(this.onJanusInitialized, this.retryInterval)
						this.retryInterval = this.retryInterval * 2
					},
					consentDialog: (on) => {
						this.waitingForConsent = on
					},
					iceState: (state) => {
						log('venueless', 'info', 'ICE state changed to ' + state)
						if (state === 'failed') {
							this.connectionState = 'failed'
							this.connectionError = `ICE connection ${state}`
							this.cleanup()
							window.setTimeout(this.onJanusInitialized, this.retryInterval)
							this.retryInterval = this.retryInterval * 2
						}
					},
					mediaState: (medium, on) => {
						log('venueless', 'info', 'Janus ' + (on ? 'started' : 'stopped') + ' receiving our ' + medium)
						if (medium === 'audio') {
							this.audioReceived = on
						}
					},
					webrtcState: (on) => {
						log('venueless', 'info', 'Janus says our WebRTC PeerConnection is ' + (on ? 'up' : 'down') + ' now')
					},
					onmessage: (msg, jsep) => {
						const event = msg.audiobridge
						if (event) {
							if (event === 'joined') {
								if (msg.id) {
									log('venueless', 'info', 'Successfully joined audiobridge ' + msg.room + ' with ID ' + msg.id)

									this.ourAudioId = msg.id
									this.connectionState = 'connected'
									this.connectionError = null

									if (this.audioPublishingState !== 'published') {
										this.publishOwnAudio()
									}

									// Any remote feeds to attach to?
									this.participants = msg.participants || []
									if (msg.participants) {
										for (const p of this.participants) {
											this.fetchUser(p)
											if (p.talking && !this.talkingParticipants.includes(p.id)) {
												this.talkingParticipants.push(p.id)
											}
										}
									}

									// start video plugin
									if (this.videoReceivingState === 'pending') {
										this.connectVideoroom()
									}
								} else {
									// someone else joined
									if (msg.participants) {
										for (const p of msg.participants) {
											this.fetchUser(p)
											if (!this.participants.find(pp => pp.id === p.id)) {
												this.participants.push(p)
											}
										}
									}
								}
							} else if (event === 'destroyed') {
								this.connectionState = 'failed'
								this.connectionError = 'Room destroyed'
								this.cleanup()
							} else if (event === 'talking') {
								if (msg.id && !this.talkingParticipants.includes(msg.id)) {
									this.talkingParticipants.push(msg.id)
								}
							} else if (event === 'stopped-talking') {
								this.talkingParticipants = this.talkingParticipants.filter(p => p !== msg.id)
							} else if (event === 'event') {
								if (msg.participants) {
									// Update e.g. muted states
									for (const p of msg.participants) {
										const exp = this.participants.find(e => e.id === p.id)
										if (exp) {
											exp.muted = p.muted
											if (p.talking && !this.talkingParticipants.includes(p.id)) {
												this.talkingParticipants.push(p.id)
											} else if (this.talkingParticipants.includes(p.id)) {
												this.talkingParticipants = this.talkingParticipants.filter(e => e !== p.id)
											}
										} else {
											this.fetchUser(p)
											this.participants.push(p.id)
										}
									}
								} else if (msg.leaving) {
									// One of the publishers has gone away?
									this.participants = this.participants.filter((rf) => rf.id !== msg.leaving)
								} else if (msg.error) {
									if (msg.error_code === 485) {
										this.connectionState = 'failed'
										this.connectionError = 'Room does not exist'
										this.cleanup()
									} else {
										this.connectionState = 'failed'
										this.connectionError = `Server error: ${msg.error}`
										this.cleanup()
									}
								}
							}
						}
						if (jsep) {
							log('venueless', 'debug', 'Handling SDP as well...', jsep)
							this.audioPluginHandle.handleRemoteJsep({jsep: jsep})
						}
					},
					slowLink: (uplink) => {
						this.upstreamSlowLinkCount++
						if (this.upstreamSlowLinkCount > 2 && this.videoRequested) {
							const newUpstreamBitrate = Math.max(this.upstreamBitrate / 2, MIN_BITRATE)
							if (newUpstreamBitrate !== this.upstreamBitrate) {
								this.upstreamBitrate = newUpstreamBitrate
								log('venueless', 'info', 'Received slowLink on outgoing audio, reducing video bitrate to ' + this.upstreamBitrate)
								const publish = {request: 'configure', audio: true, video: this.publishingWithVideo, bitrate: this.upstreamBitrate}
								this.videoPluginHandle.send({message: publish})
								this.upstreamSlowLinkCount = 0
							} else {
								if (this.upstreamSlowLinkCount > 5) {
									log('venueless', 'info', 'Received slowLink on outgoing audio, video bitrate already at minimum, turning video off')
									this.videoRequested = false
									this.publishOwnVideo()
								} else {
									log('venueless', 'info', 'Received slowLink on outgoing audio, video bitrate already at minimum')
								}
							}
						}
					},
					onlocalstream: (stream) => {
						// Ignore our own audio stream, we don't want an echo, let's just confirm that it's there
						if (this.audioPluginHandle.webrtcStuff.pc.iceConnectionState !== 'completed' &&
							this.audioPluginHandle.webrtcStuff.pc.iceConnectionState !== 'connected') {
							this.audioPublishingState = 'publishing'
						} else {
							if (this.audioReceived) {
								this.audioPublishingState = 'published'
								this.publishingError = null
							}
						}
						if (this.knownMuteState) {
							// Mute client side as well as server side
							this.audioPluginHandle.muteAudio()
						}
					},
					onremotestream: (stream) => {
						this.audioReceivingState = 'receiving'
						Janus.attachMediaStream(this.$refs.mixedAudio, stream)
						if (localStorage.audioOutput) {
							if (this.$refs.mixedAudio.setSinkId) { // chrome only for now
								this.$refs.mixedAudio.setSinkId(localStorage.audioOutput)
							}
						}
					},
					oncleanup: () => {
						log('venueless', 'info', ' ::: Got a cleanup notification: we are unpublished now :::')
						this.audioPublishingState = 'unpublished'
					},
				})
		},
		connectVideoroom () {
			// Roughly based on https://janus.conf.meetecho.com/videoroomtest.js
			this.janus.attach(
				{
					plugin: 'janus.plugin.videoroom',
					opaqueId: this.ourAudioId,
					success: (pluginHandle) => {
						this.videoPluginHandle = pluginHandle
						log('venueless', 'info', 'Plugin attached! (' + this.videoPluginHandle.getPlugin() + ', id=' + this.videoPluginHandle.getId() + ')')

						const register = {
							request: 'join',
							room: this.roomId,
							id: this.sessionId,
							ptype: 'publisher',
							token: this.token,
							display: 'venueless user',
						}
						this.videoPluginHandle.send({message: register})
					},
					error: (error) => {
						this.videoReceivingState = 'failed'
						this.connectionError = error
					},
					consentDialog: (on) => {
						this.waitingForConsent = on
					},
					iceState: (state) => {
						log('venueless', 'info', 'ICE state changed to ' + state)
						if (state === 'failed') {
							// todo correct?
							this.videoReceivingState = 'failed'
							this.connectionError = `ICE connection ${state}`
							this.cleanup()
							window.setTimeout(this.onJanusInitialized, this.retryInterval)
							this.retryInterval = this.retryInterval * 2
						}
					},
					mediaState: (medium, on) => {
						log('venueless', 'info', 'Janus ' + (on ? 'started' : 'stopped') + ' receiving our ' + medium)
						if (medium === 'video') {
							this.videoReceived = on
						}
						if (this.videoReceived) {
							this.videoPublishingState = 'published'
							this.publishingError = null
						} else if (!this.videoReceived && !this.videoRequested) {
							this.videoPublishingState = 'unpublished'
						}
					},
					webrtcState: (on) => {
						log('venueless', 'info', 'Janus says our WebRTC PeerConnection is ' + (on ? 'up' : 'down') + ' now')
					},
					onmessage: (msg, jsep) => {
						const event = msg.videoroom
						if (event) {
							if (event === 'joined') {
								log('venueless', 'info', 'Successfully joined room ' + msg.room + ' with ID ' + msg.id)

								// Publisher/manager created, negotiate WebRTC and attach to existing feeds, if any
								this.ourId = msg.id
								this.ourPrivateId = msg.private_id

								this.videoReceivingState = 'receiving'

								// Any remote feeds to attach to?
								if (msg.publishers) {
									this.videoPublishers = msg.publishers
									for (const f of msg.publishers) {
										this.subscribeRemoteVideo(f.id, f.display, f.audio_codec, f.video_codec)
									}
								}
								this.publishOwnVideo()
							} else if (event === 'destroyed') {
								this.videoReceivingState = 'failed'
								this.connectionError = 'Room destroyed'
								this.cleanup()
							} else if (event === 'event') {
								// Any new feed to attach to?
								if (msg.publishers) {
									for (const f of msg.publishers) {
										this.videoPublishers.push(f)
										this.subscribeRemoteVideo(f.id, f.display, f.audio_codec, f.video_codec)
									}
								} else if (msg.leaving) {
									// One of the publishers has gone away?
									const leaving = msg.leaving
									this.videoPublishers = this.videoPublishers.filter((rf) => rf.id !== leaving)
									const remoteFeed = this.feeds.find((rf) => rf.rfid === leaving)
									if (remoteFeed != null) {
										log('venueless', 'debug',
											'Feed ' + remoteFeed.rfid + ' (' + remoteFeed.rfdisplay + ') has left the room, detaching')
										this.feeds = this.feeds.filter((rf) => rf.rfid !== remoteFeed.rfid)
										remoteFeed.detach()
									}
								} else if (msg.unpublished) {
									// One of the publishers has unpublished?
									const unpublished = msg.unpublished
									if (unpublished === 'ok') {
										// That's us
										this.videoPublishingState = 'unpublished'
										this.publishingError = null
										this.videoPluginHandle.hangup()
										return
									}
									this.videoPublishers = this.videoPublishers.filter((rf) => rf.id !== unpublished)
									const remoteFeed = this.feeds.find((rf) => rf.rfid === unpublished)
									if (remoteFeed != null) {
										log('venueless', 'debug', 'Feed ' + remoteFeed.rfid + ' (' + remoteFeed.rfdisplay + ') has left the room, detaching')
										this.feeds = this.feeds.filter((rf) => rf.rfid !== remoteFeed.rfid)
										remoteFeed.detach()
									}
								} else if (msg.error) {
									if (msg.error_code === 426) {
										this.videoReceivingState = 'failed'
										this.connectionError = 'Room does not exist'
									} else {
										this.videoReceivingState = 'failed'
										this.connectionError = `Server error: ${msg.error}`
									}
								}
							}
						}
						if (jsep) {
							log('venueless', 'debug', 'Handling SDP as well...', jsep)
							this.videoPluginHandle.handleRemoteJsep({jsep: jsep})
							// Check if any of the media we wanted to publish has
							// been rejected (e.g., wrong or unsupported codec)
							var video = msg.video_codec
							if (this.ourStream && this.ourStream.getVideoTracks() && this.ourStream.getVideoTracks().length > 0 &&
								!video) {
								// todo: log, show error to user?
								this.videoRequested = false
								this.publishingWithVideo = false
							}
						}
					},
					slowLink: (uplink) => {
						this.upstreamSlowLinkCount++
						if (this.upstreamSlowLinkCount > 2) {
							const newUpstreamBitrate = Math.max(this.upstreamBitrate / 2, MIN_BITRATE)
							if (newUpstreamBitrate !== this.upstreamBitrate) {
								this.upstreamBitrate = newUpstreamBitrate
								log('venueless', 'info', 'Received slowLink on outgoing video, reducing bitrate to ' + this.upstreamBitrate)
								const publish = {request: 'configure', audio: true, video: this.publishingWithVideo, bitrate: this.upstreamBitrate}
								this.videoPluginHandle.send({message: publish})
								this.upstreamSlowLinkCount = 0
							} else {
								if (this.upstreamSlowLinkCount > 5) {
									log('venueless', 'info', 'Received slowLink on outgoing video, bitrate already at minimum, turning video off')
									this.videoRequested = false
									this.publishOwnVideo()
								} else {
									log('venueless', 'info', 'Received slowLink on outgoing video, bitrate already at minimum')
								}
							}
						}
					},
					onlocalstream: (stream) => {
						this.ourStream = stream
						if (this.videoPluginHandle.webrtcStuff.pc && this.videoPluginHandle.webrtcStuff.pc.iceConnectionState !== 'completed' &&
							this.videoPluginHandle.webrtcStuff.pc.iceConnectionState !== 'connected') {
							this.videoPublishingState = 'publishing'
						} else {
							if ((this.videoReceived || !this.publishingWithVideo) && this.audioReceived) {
								this.videoPublishingState = 'published'
								this.publishingError = null
							}
						}
						if (this.automute) {
							this.videoPluginHandle.muteAudio()
						}
						const videoTracks = stream.getVideoTracks()
						if (!videoTracks || videoTracks.length === 0) {
							this.videoRequested = false
							this.publishingWithVideo = false
						} else {
							Janus.attachMediaStream(this.$refs.ourVideo, stream)
						}
					},
					oncleanup: () => {
						log('venueless', 'info', ' ::: Got a cleanup notification: we are unpublished now :::')
						this.videoPublishingState = 'unpublished'
					},
				})
		},
		onJanusInitialized () {
			this.connectionState = 'connecting'
			Janus.trace = (t) => log('janus', 'trace', t)
			Janus.debug = (t) => log('janus', 'debug', t)
			Janus.vdebug = (t) => log('janus', 'vdebug', t)
			Janus.log = (t) => log('janus', 'log', t)
			Janus.warn = (t) => log('janus', 'warn', t)
			Janus.error = (t) => log('janus', 'error', t)
			this.janus = new Janus({
				server: this.server,
				iceServers: this.iceServers,
				success: this.onJanusConnected,
				error: (error) => {
					this.connectionState = 'failed'
					this.connectionError = error.message
					this.cleanup()
					window.setTimeout(this.onJanusInitialized, this.retryInterval)
					this.retryInterval = this.retryInterval * 2
				},
				destroyed: () => {
					this.connectionState = 'disconnected'
				},
			})
		},
		initJanus () {
			this.connectionState = 'connecting'
			Janus.init({
				debug: 'all', // todo: conditional
				callback: this.onJanusInitialized,
			})
		},
		async fetchUser (feed) {
			const uid = feed.rfid || feed.id
			let user = this.userCache[uid]
			if (!user) {
				user = await api.call('januscall.identify', {id: uid})
				this.userCache[uid] = user
			}
			feed.venueless_user = user
			const rfindex = this.feeds.findIndex((rf) => rf.rfid === feed.rfid)
			this.$set(this.feeds, rfindex, feed) // force reactivity
		},
	},
}
</script>
<style lang="stylus">
.c-janusconference
	flex: auto 1 1
	height: 100% // todo: test in safari
	display: flex
	flex-direction: column
	position: relative

	.controlbar
		width: auto
		margin: auto
		flex-shrink: 0
		card()
		.bunt-icon-button
			line-height: 42px
			height: 42px
			width: 42px
		.bunt-icon-button .bunt-icon
			font-size: 26px
		.hangup
			color: $clr-danger

	.connection-state
		padding: 16px
		display: flex
		justify-content: center
		align-content: center
		align-items: center
		max-height: 100%
		flex: auto 1 1

	.participants
		padding: 5px 15px

		.participant
			position: relative
			cursor: pointer
			display: inline-block
			margin: 5px
			border: 4px solid transparent
			border-radius: 50%

			&.talking
				border: 4px solid var(--clr-primary)

			.mute-indicator
				position: absolute
				right: 0px
				bottom: 0px
				background: $clr-danger
				width: 16px
				height: 16px
				border-radius: 50%
				text-align: center
				.bunt-icon
					width: 100%
					color: white
					line-height: 16px
					font-size: 12px

	.users
		padding: 16px
		display: flex
		justify-content: center
		align-content: center
		flex-wrap: wrap
		height: auto
		max-height: 100%
		flex: auto 1 1
		overflow: hidden
		position: relative

	.slow-banner
		box-sizing: border-box
		background: #666
		color: white
		cursor: pointer
		padding: 8px
		position: absolute
		left: 0
		top: 0
		text-align: center
		width: 100%

	.users .feed
		width: var(--video-width)
		height: var(--video-height)
		padding: 8px
		position: relative

		.mute-indicator
			position: absolute
			right: 16px
			bottom: 16px
			background: black
			opacity: 0.5
			width: 32px
			height: 32px
			max-width: 100%
			max-height: 100%
			border-radius: 50%
			text-align: center
			.bunt-icon
				width: 100%
				color: white
				line-height: 32px
				font-size: 20px

		.publishing-state, .subscribing-state
			position: absolute
			left: 0
			top: 0
			height: 100%
			width: 100%
			display: flex
			justify-content: center
			align-content: center
			align-items: center
			.publishing-error
				background: rgba(0, 0, 0, 0.8)
				width: 80%
				padding: 16px
				text-align: center
				color: white

		.controls
			display: flex
			align-items: center
			padding: 0 8px 0 16px
			min-height: 48px
			position: absolute
			top: 20px
			left: 50%
			transform: translate(-50%)
			opacity: 0
			transition: opacity .5s
			card()

			.user
				display: flex
				cursor: pointer
				align-items: center
				height: 100%
				margin-right: 16px
				.display-name
					margin-left: 8px
					flex: auto
					ellipsis()

		&:hover .controls
			transition: opacity .5s
			opacity: 1

		.video-container
			background: #000
			width: 100%
			height: 100%
			position: relative
			overflow: hidden
			border-radius: 5px

			video
				max-height: 100%
				max-width: 100%
				height: 100%
				object-fit: contain
				width: 100%

	.users .feed.me
		.video-container video
			transform: rotateY(180deg)

	.size-tiny &
		.participants
			display: none
		.users
			padding: 0
			margin: 0
			.feed
				padding: 0
				width: var(--video-width)
				height: var(--video-height)
				.video-container
					border-radius: 0
		.controlbar, .controls, .mute-indicator, .novideo-indicator
			display: none
</style>

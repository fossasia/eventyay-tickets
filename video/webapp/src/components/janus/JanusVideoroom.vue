<template lang="pug">
.c-janusvideoroom

	.connection-state(v-if="connectionState != 'connected'")
		div(v-if="connectionState == 'disconnected'") {{ $t('JanusVideoroom:disconnected:text') }}
		div.connection-error(v-else-if="connectionState == 'failed'")
			p {{ $t('JanusVideoroom:connection-error:text') }}
			p {{ connectionError }}
		bunt-progress-circular(v-else-if="connectionState == 'connecting'", size="huge", :page="true")

	.users(v-show="connectionState == 'connected'", ref="container", :style="gridStyle", v-resize-observer="onResize")

		.me.feed
			.video-container(:style="{boxShadow: size != 'tiny' ? `0 0 0px 4px ${primaryColor.alpha(soundLevels.ourVideo * 20)}` : 'none'}")
				video(v-show="publishingWithVideo && publishingState !== 'unpublished'", ref="ourVideo", autoplay, playsinline, muted="muted")
			.publishing-state(v-if="publishingState !== 'published'")
				bunt-progress-circular(v-if="publishingState == 'publishing'", size="huge", :page="true")
				div.publishing-error(v-else-if="publishingState == 'failed'")
					p {{ $t('JanusVideoroom:publishing-error:text') }}
					p {{ publishingError }}
			.controls
				.user(@click="showUserCard($event, user)")
					avatar(:user="user", :size="36")
					span.display-name {{ user.profile.display_name }}
				bunt-icon-button(@click="requestFullscreen($refs.ourVideo)") fullscreen
			.novideo-indicator(v-if="publishingState == 'published' && !publishingWithVideo")
				avatar(:user="user", :size="96")
			.mute-indicator(v-if="knownMuteState")
				.bunt-icon.mdi.mdi-microphone-off

		.peer.feed(v-for="(f, idx) in feeds", :key="f.rfid", :style="{width: layout.width, height: layout.height}")
			.video-container(v-show="f.rfattached", :style="{boxShadow: size != 'tiny' ? `0 0 0px 4px ${primaryColor.alpha(soundLevels[f.rfid] * 20)}` : 'none'}")
				video(ref="peerVideo", autoplay, playsinline)
			.subscribing-state(v-if="!f.rfattached")
				bunt-progress-circular(size="huge", :page="true")
			.novideo-indicator(v-if="f.rfattached && !f.hasVideo && f.venueless_user !== null")
				avatar(:user="f.venueless_user", :size="96")
			.controls
				.user(v-if="f.venueless_user !== null", @click="showUserCard($event, f.venueless_user)")
					avatar(:user="f.venueless_user", :size="36")
					span.display-name {{ f.venueless_user.profile.display_name }}
				bunt-icon-button(@click="requestFullscreen($refs.peerVideo[idx])") fullscreen

	.controlbar.controls(v-show="connectionState == 'connected'", :class="knownMuteState ? 'always' : ''")
		bunt-icon-button(@click="toggleVideo") {{ !videoRequested ? 'video-off' : 'video' }}
		bunt-icon-button(@click="toggleMute") {{ knownMuteState ? 'microphone-off' : 'microphone' }}
		bunt-icon-button(@click="toggleScreenShare", :disabled="screensharingState === 'publishing' || screensharingState === 'unpublishing'") {{ screensharingState === 'published' ? 'monitor-off': 'monitor' }}
		bunt-icon-button(@click="showDevicePrompt = true") cog
		bunt-icon-button(@click="cleanup(); $emit('hangup')") phone-hangup

	chat-user-card(v-if="selectedUser", ref="avatarCard", :sender="selectedUser", @close="selectedUser = null")
	transition(name="prompt")
		a-v-device-prompt(v-if="showDevicePrompt", @close="closeDevicePrompt")
</template>
<script>
import {Janus} from 'janus-gateway'
import {mapState} from 'vuex'
import api from 'lib/api'
import ChatUserCard from 'components/ChatUserCard'
import Avatar from 'components/Avatar'
import AVDevicePrompt from 'components/AVDevicePrompt'
import {createPopper} from '@popperjs/core'
import SoundMeter from 'lib/webrtc/soundmeter'
import Color from 'color'
import {colors} from 'theme'

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

export default {
	components: {Avatar, AVDevicePrompt, ChatUserCard},
	props: {
		server: {
			type: String,
			required: true
		},
		token: {
			type: String,
			required: true
		},
		roomId: {
			type: Number,
			required: true
		},
		iceServers: {
			type: Array,
			required: true
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
			publishingState: 'unpublished', // unpublished, publishing, published, failed
			screensharingState: 'unpublished', // unpublished, publishing, published, unpublishing, failed

			// Error handling
			retryInterval: 1000,
			connectionError: null,
			connectionRetryTimeout: null,
			publishingError: null,
			screensharingError: null,

			// References to Janus.js
			janus: null,
			mainPluginHandle: null,
			screensharePluginHandle: null,

			// Video controls state
			videoRequested: true, // user *wants* to send video

			// Janus video call state
			feeds: [],
			ourId: null,
			ourPrivateId: null,
			ourStream: null,
			ourScreenShareStream: null,
			knownMuteState: false,
			publishingWithVideo: false, // we are *trying* to send video
			videoReceived: false, // janus *has* received our video
			audioReceived: true, // janus *has* received our audio
			videoInput: null, // video input currently requested from janus
			audioInput: null, // audio input currently requested from janus
			videoOutput: localStorage.videoOutput !== 'false',
			waitingForConsent: false,

			// Sound metering
			soundMeters: {},
			soundLevels: {},
			soundMeterInterval: null,

			// Layout utilities
			primaryColor: Color(colors.primary),
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
		}
	},
	destroyed () {
		if (this.janus) {
			this.cleanup()
		}
		if (this.connectionRetryTimeout) {
			window.clearTimeout(this.connectionRetryTimeout)
		}
		if (this.soundMeterInterval) {
			window.clearInterval(this.soundMeterInterval)
		}
	},
	mounted () {
		if (this.janus) {
			this.cleanup()
		}
		this.initJanus()
		this.soundMeterInterval = window.setInterval(() => {
			for (const idx in this.soundMeters) {
				this.$set(this.soundLevels, idx, this.soundMeters[idx].slow.toFixed(2))
			}
		}, 200)
	},
	methods: {
		cleanup () {
			this.janus.destroy({cleanupHandles: true})
			this.connectionState = 'disconnected'
			this.publishingState = 'unpublished'
			this.screensharingState = 'unpublished'
			this.retryInterval = 1000
			this.connectionError = null
			this.screensharingError = null
			this.feeds = []
			this.ourStream = null
			this.ourScreenShareStream = null
			for (const idx in this.soundMeters) {
				this.soundMeters[idx].context.close()
			}
			this.soundMeters = {}
		},
		onResize () {
			const bbox = this.$refs.container.getBoundingClientRect()
			this.layout = calculateLayout(
				this.size === 'tiny' ? bbox.width : bbox.width - 16 * 2,
				this.size === 'tiny' ? bbox.height : bbox.height - 16 * 2,
				this.feeds.length + 1,
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
				// it's probably possible to do this without a full reconnect, but it's probably hard
				this.cleanup()
				this.videoOutput = (localStorage.videoOutput !== 'false')
				this.onJanusInitialized()
			}
			this.publishOwnFeed()
			if (typeof this.$refs.peerVideo !== 'undefined') {
				for (let i = 0; i < this.$refs.peerVideo.length; i++) {
					if (this.$refs.peerVideo[i].setSinkId) { // chrome only for now
						this.$refs.peerVideo[i].setSinkId(localStorage.audioOutput || '')
					}
				}
			}
		},
		async showUserCard (event, user) {
			this.selectedUser = user
			await this.$nextTick()
			const target = event.target.closest('.user')
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
							Janus.log(
								'Plugin attached! (' + this.screensharePluginHandle.getPlugin() + ', id=' + this.mainPluginHandle.getId() + ')')

							const register = {
								request: 'join',
								room: this.roomId,
								ptype: 'publisher',
								token: this.token,
								display: this.user.id, // we abuse janus' display name field for the venueless user id
							}
							this.screensharePluginHandle.send({message: register})
						},
						error: (error) => {
							Janus.error('  -- Error attaching plugin...', error)
							alert('Screen sharing failed (error: ' + error.message + ')')
						},
						consentDialog: (on) => {
							this.waitingForConsent = on
						},
						iceState: (state) => {
							Janus.log('ICE state changed to ' + state)
							// if state "failed", show user, unless we're currently leaving the room
						},
						mediaState: (medium, on) => {
							Janus.log('Janus ' + (on ? 'started' : 'stopped') + ' receiving our ' + medium)
							if (medium === 'video' && on) {
								this.screensharingState = 'published'
							}
						},
						webrtcState: (on) => {
							Janus.log('Janus says our WebRTC PeerConnection is ' + (on ? 'up' : 'down') + ' now')
						},
						onmessage: (msg, jsep) => {
							Janus.debug(' ::: Got a message (publisher) :::', msg)
							var event = msg.videoroom
							Janus.debug('Event: ' + event)
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
										Janus.log('Publisher left: ' + unpublished)
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
								Janus.debug('Handling SDP as well...', jsep)
								this.screensharePluginHandle.handleRemoteJsep({jsep: jsep})
								var audio = msg.audio_codec
								if (this.ourScreenShareStream && this.ourScreenShareStream.getAudioTracks() && this.ourScreenShareStream.getAudioTracks().length > 0 &&
									!audio) {
									// Audio has been rejected
									console.warning('Our audio stream has been rejected, viewers won\'t hear our screenshare')
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
							Janus.debug(' ::: Got a local stream :::', stream)
							this.ourScreenShareStream = stream
							// todo: show local stream instead of remote Stream
						},
						oncleanup: () => {
							Janus.log(' ::: Got a cleanup notification: we are unpublished now :::')
							this.ourScreenShareStream = null
							this.screensharingState = 'unpublished'
						},
					})
			}
		},
		toggleVideo () {
			this.videoRequested = !this.videoRequested
			this.publishOwnFeed()
		},
		toggleMute () {
			if (this.mainPluginHandle == null) {
				return
			}
			this.knownMuteState = this.mainPluginHandle.isAudioMuted()
			if (this.knownMuteState) {
				this.mainPluginHandle.unmuteAudio()
			} else {
				this.mainPluginHandle.muteAudio()
			}
			this.knownMuteState = this.mainPluginHandle.isAudioMuted()
		},
		publishOwnFeed () {
			const media = {
				audioRecv: false,
				videoRecv: false,
				audioSend: true,
				videoSend: this.videoRequested,
			}

			if (this.videoRequested) {
				if (localStorage.videoInput) {
					media.video = {deviceId: localStorage.videoInput, width: 1280, height: 720}
				} else {
					media.video = 'hires'
				}
				if (this.publishingState !== 'unpublished' && !this.publishingWithVideo) {
					media.addVideo = true
				} else if (localStorage.videoInput !== this.videoInput) {
					media.replaceVideo = true
					this.videoInput = localStorage.videoInput
				}
			} else if (this.publishingWithVideo) {
				media.removeVideo = true
			}

			if (localStorage.audioInput) {
				media.audio = {deviceId: localStorage.audioInput}
			}
			if (localStorage.audioInput !== this.audioInput) {
				media.replaceAudio = true
				this.audioInput = localStorage.audioInput
			}

			this.publishingWithVideo = this.videoRequested
			this.publishingState = 'publishing'

			this.mainPluginHandle.createOffer(
				{
					media: media,
					// If you want to test simulcasting (Chrome and Firefox only), set to true
					simulcast: false,
					simulcast2: false,
					success: (jsep) => {
						const publish = {request: 'configure', audio: true, video: this.publishingWithVideo}
						this.mainPluginHandle.send({message: publish, jsep: jsep})
					},
					error: (error) => {
						if (this.publishingWithVideo) {
							this.videoRequested = false
							this.publishOwnFeed()
						} else {
							this.publishingState = 'failed'
							this.publishingError = error.message
						}
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
						Janus.debug('Got publisher SDP!', jsep)
						var publish = {request: 'configure', audio: true, video: true}
						this.screensharePluginHandle.send({message: publish, jsep: jsep})
					},
					error: (error) => {
						Janus.error('WebRTC error:', error)
						alert('Screen sharing failed (error: ' + error.message + ')')
						this.screensharingState = 'failed'
					},
				})
		},
		onNewRemoteFeed (id, display, audio, video) {
			// A new feed has been published, create a new plugin handle and attach to it as a subscriber
			let remoteFeed = null
			this.janus.attach({
				plugin: 'janus.plugin.videoroom',
				opaqueId: this.user.id,
				success: (pluginHandle) => {
					remoteFeed = pluginHandle
					remoteFeed.simulcastStarted = false
					Janus.log('Plugin attached! (' + remoteFeed.getPlugin() + ', id=' + remoteFeed.getId() + ')')
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
					subscribe.offer_video = this.videoOutput
					// For example, if the publisher is VP8 and this is Safari, let's avoid video
					if (Janus.webRTCAdapter.browserDetails.browser === 'safari' &&
						(video === 'vp9' || (video === 'vp8' && !Janus.safariVp8))) {
						if (video)
							video = video.toUpperCase()
						console.log('Publisher is using ' + video + ', but Safari doesn\'t support it: disabling video')
						subscribe.offer_video = false
					}
					remoteFeed.videoCodec = video
					remoteFeed.send({message: subscribe})
				},
				error: (error) => {
					Janus.error('  -- Error attaching plugin...', error)
					alert('Error attaching plugin... ' + error)
				},
				onmessage: (msg, jsep) => {
					Janus.debug(' ::: Got a message (subscriber) :::', msg)
					var event = msg.videoroom
					Janus.debug('Event: ' + event)
					if (msg.error) {
						console.error('Error when subscribing: ' + msg.error)
						// todo: show something?
					} else if (event) {
						if (event === 'attached') {
							// Subscriber created and attached
							remoteFeed.rfattached = false
							remoteFeed.hasVideo = false
							remoteFeed.rfid = msg.id
							remoteFeed.venueless_user_id = msg.display
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
						Janus.debug('Handling SDP as well...', jsep)
						// Answer and attach
						remoteFeed.createAnswer({
							jsep: jsep,
							// Add data:true here if you want to subscribe to datachannels as well
							// (obviously only works if the publisher offered them in the first place)
							media: {audioSend: false, videoSend: false},	// We want recvonly audio/video
							success: (jsep) => {
								Janus.debug('Got SDP!', jsep)
								var body = {request: 'start', room: this.roomId}
								remoteFeed.send({message: body, jsep: jsep})
							},
							error: (error) => {
								Janus.error('WebRTC error:', error)
								alert('WebRTC error... ' + error.message)
							},
						})
					}
				},
				iceState: (state) => {
					Janus.log(
						'ICE state of this WebRTC PeerConnection (feed #' + remoteFeed.rfid + ') changed to ' + state)
				},
				webrtcState: (on) => {
					Janus.log(
						'Janus says this WebRTC PeerConnection (feed #' + remoteFeed.rfid + ') is ' + (on ? 'up' : 'down') +
						' now')
				},
				onremotestream: (stream) => {
					Janus.debug('Remote feed #' + remoteFeed.rfid + ', stream:', stream)
					const rfindex = this.feeds.findIndex((rf) => rf.rfid === remoteFeed.rfid)
					this.$nextTick(() => {
						Janus.attachMediaStream(this.$refs.peerVideo[rfindex], stream)
						if (localStorage.audioOutput) {
							if (this.$refs.peerVideo[rfindex].setSinkId) { // chrome only for now
								this.$refs.peerVideo[rfindex].setSinkId(localStorage.audioOutput)
							}
						}
						remoteFeed.rfattached = true
						const videoTracks = stream.getVideoTracks()
						if (!videoTracks || videoTracks.length === 0) {
							remoteFeed.hasVideo = false
						} else {
							remoteFeed.hasVideo = true
						}
						this.initSoundMeter(stream, remoteFeed.rfid)
					})
				},
			})
		},
		onJanusConnected () {
			// Roughly based on https://janus.conf.meetecho.com/videoroomtest.js
			this.janus.attach(
				{
					plugin: 'janus.plugin.videoroom',
					opaqueId: this.user.id,
					success: (pluginHandle) => {
						this.mainPluginHandle = pluginHandle
						Janus.log(
							'Plugin attached! (' + this.mainPluginHandle.getPlugin() + ', id=' + this.mainPluginHandle.getId() + ')')

						const register = {
							request: 'join',
							room: this.roomId,
							ptype: 'publisher',
							token: this.token,
							display: this.user.id, // we abuse janus' display name field for the venueless user id
						}
						this.mainPluginHandle.send({message: register})
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
						Janus.log('ICE state changed to ' + state)
						if (state === 'failed') {
							// todo correct?
							this.connectionState = 'failed'
							this.connectionError = `ICE connection ${state}`
							this.cleanup()
							window.setTimeout(this.onJanusInitialized, this.retryInterval)
							this.retryInterval = this.retryInterval * 2
						}
					},
					mediaState: (medium, on) => {
						Janus.log('Janus ' + (on ? 'started' : 'stopped') + ' receiving our ' + medium)
						if (medium === 'video') {
							this.videoReceived = on
						}
						if (medium === 'audio') {
							this.audioReceived = on
						}
						if ((this.videoReceived || !this.publishingWithVideo) && this.audioReceived) {
							this.publishingState = 'published'
							this.publishingError = null
						}
					},
					webrtcState: (on) => {
						Janus.log('Janus says our WebRTC PeerConnection is ' + (on ? 'up' : 'down') + ' now')
					},
					onmessage: (msg, jsep) => {
						const event = msg.videoroom
						if (event) {
							if (event === 'joined') {
								Janus.log('Successfully joined room ' + msg.room + ' with ID ' + this.ourId)

								// Publisher/manager created, negotiate WebRTC and attach to existing feeds, if any
								this.ourId = msg.id
								this.ourPrivateId = msg.private_id

								this.connectionState = 'connected'
								this.connectionError = null

								// Any remote feeds to attach to?
								if (msg.publishers) {
									var list = msg.publishers
									for (const f of list) {
										this.onNewRemoteFeed(f.id, f.display, f.audio_codec, f.video_codec)
									}
								}
								this.publishOwnFeed()
							} else if (event === 'destroyed') {
								this.connectionState = 'failed'
								this.connectionError = 'Room destroyed'
								this.cleanup()
							} else if (event === 'event') {
								// Any new feed to attach to?
								if (msg.publishers) {
									const list = msg.publishers
									for (const f of list) {
										this.onNewRemoteFeed(f.id, f.display, f.audio_codec, f.video_codec)
									}
								} else if (msg.leaving) {
									// One of the publishers has gone away?
									const leaving = msg.leaving
									const remoteFeed = this.feeds.find((rf) => rf.rfid === leaving)
									if (remoteFeed != null) {
										Janus.debug(
											'Feed ' + remoteFeed.rfid + ' (' + remoteFeed.rfdisplay + ') has left the room, detaching')
										this.feeds = this.feeds.filter((rf) => rf.rfid !== remoteFeed.rfid)
										remoteFeed.detach()
									}
								} else if (msg.unpublished) {
									// One of the publishers has unpublished?
									const unpublished = msg.unpublished
									if (unpublished === 'ok') {
										// That's us
										this.publishingState = 'unpublished'
										this.publishingError = null
										this.mainPluginHandle.hangup()
										return
									}
									const remoteFeed = this.feeds.find((rf) => rf.rfid === unpublished)
									if (remoteFeed != null) {
										Janus.debug(
											'Feed ' + remoteFeed.rfid + ' (' + remoteFeed.rfdisplay + ') has left the room, detaching')
										this.feeds = this.feeds.filter((rf) => rf.rfid !== remoteFeed.rfid)
										remoteFeed.detach()
									}
								} else if (msg.error) {
									if (msg.error_code === 426) {
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
							Janus.debug('Handling SDP as well...', jsep)
							this.mainPluginHandle.handleRemoteJsep({jsep: jsep})
							// Check if any of the media we wanted to publish has
							// been rejected (e.g., wrong or unsupported codec)
							var audio = msg.audio_codec
							if (this.ourStream && this.ourStream.getAudioTracks() && this.ourStream.getAudioTracks().length > 0 &&
								!audio) {
								// todo: log, show error to user?
							}
							var video = msg.video_codec
							if (this.ourStream && this.ourStream.getVideoTracks() && this.ourStream.getVideoTracks().length > 0 &&
								!video) {
								// todo: log, show error to user?
								this.videoRequested = false
								this.publishingWithVideo = false
							}
						}
					},
					onlocalstream: (stream) => {
						this.ourStream = stream
						if (this.mainPluginHandle.webrtcStuff.pc.iceConnectionState !== 'completed' &&
							this.mainPluginHandle.webrtcStuff.pc.iceConnectionState !== 'connected') {
							this.publishingState = 'publishing'
						} else {
							if ((this.videoReceived || !this.publishingWithVideo) && this.audioReceived) {
								this.publishingState = 'published'
								this.publishingError = null
							}
						}
						const videoTracks = stream.getVideoTracks()
						if (!videoTracks || videoTracks.length === 0) {
							this.videoRequested = false
							this.publishingWithVideo = false
						} else {
							Janus.attachMediaStream(this.$refs.ourVideo, stream)
							this.$refs.ourVideo.muted = 'muted' // no echo
							this.knownMuteState = this.mainPluginHandle.isAudioMuted()
						}
						this.initSoundMeter(stream, 'ourVideo')
					},
					oncleanup: () => {
						Janus.log(' ::: Got a cleanup notification: we are unpublished now :::')
						this.publishingState = 'unpublished'
					},
				})
		},
		initSoundMeter (stream, refname) {
			const atracks = stream.getAudioTracks()
			if (!atracks || atracks.length === 0) {
				return
			}
			window.AudioContext = window.AudioContext || window.webkitAudioContext
			const actx = new AudioContext()
			const soundmeter = new SoundMeter(actx)
			soundmeter.connectToSource(stream)
			this.$set(this.soundMeters, refname, soundmeter)
		},
		onJanusInitialized () {
			this.connectionState = 'connecting'
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
			this.$set(feed, 'venueless_user', await api.call('user.fetch', {id: feed.venueless_user_id}))
		},
	},
}
</script>
<style lang="stylus">
.c-janusvideoroom
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

	.connection-state
		padding: 16px
		display: flex
		justify-content: center
		align-content: center
		align-items: center
		max-height: 100%
		flex: auto 1 1

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

	.users .feed
		width: var(--video-width)
		height: var(--video-height)
		padding: 8px
		position: relative

		.novideo-indicator
			position: absolute
			left: 50%
			top: 50%
			transform: translate(-50%, -50%)
			background: white
			padding: 12px
			border-radius: 50%
			text-align: center
			height: 96px
			width: 96px

		.mute-indicator
			position: absolute
			right: 16px
			bottom: 16px
			background: black
			opacity: 0.5
			width: 32px
			height: 32px
			border-radius: 16px
			text-align: center
			.bunt-icon
				color: white
				line-height: 32px

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

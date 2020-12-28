<template lang="pug">
.c-roulette
	.users(v-show="roomId != null")
		.me
			bunt-progress-circular(size="large", :page="true")
			p {{ $t('Roulette:waiting-own:label') }}
			video(v-show="ourVideoVisible", ref="ourVideo", autoplay, playsinline, muted="muted")
			.controls(:class="knownMuteState ? 'always' : ''")
				bunt-icon-button(@click="toggleMute") {{ knownMuteState ? 'microphone-off' : 'microphone' }}
				bunt-icon-button(@click="showDevicePrompt = true") cog
		.peer(v-for="f in feeds", :key="f.rfid")
			video(ref="peerVideo", autoplay, playsinline)
			div {{f.venueless_user}}
			.user(v-if="f.venueless_user !== null", @click="showUserCard($event, f.venueless_user)")
				avatar(:user="f.venueless_user", :size="36")
				span.display-name {{ f.venueless_user.profile.display_name }}
		.no-peer(v-if="!feeds.length")
			bunt-progress-circular(size="large", :page="true")
			p {{ $t('Roulette:waiting-other:label') }}
	.next
		bunt-button.btn-next(@click="startNewCall", :error-message="joinError", :loading="loading") {{ $t('Roulette:btn-start:label') }}
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

export default {
	components: {Avatar, AVDevicePrompt, ChatUserCard},
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
			server: null,
			token: null,
			iceServers: [],
			roomId: null,
			loading: false,
			janus: null,
			pluginHandle: null,
			ourId: null,
			ourPrivateId: null,
			ourVideoVisible: true,
			knownMuteState: false,
			joinError: null,
			feeds: [],
			selectedUser: null,
			videoInput: null,
			audioInput: null,
		}
	},
	computed: {
		...mapState(['user']),
	},
	async mounted () {
		// todo fetch from server
	},
	destroyed () {
		if (this.janus) {
			this.janus.destroy()
		}
	},
	methods: {
		closeDevicePrompt () {
			this.showDevicePrompt = false
			this.publishOwnFeed(true)
			for (let i = 0; i < this.$refs.peerVideo.length; i++) {
				if (this.$refs.peerVideo[i].setSinkId) { // chrome only for now
					this.$refs.peerVideo[i].setSinkId(localStorage.audioOutput || '')
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
		async startNewCall () {
			if (this.janus) {
				this.janus.destroy()
				this.janus = null
				this.server = null
				this.roomId = null
				this.feeds = []
			}
			this.loading = true
			this.joinError = null
			try {
				const {server, roomId, token, iceServers} = await api.call('roulette.start', {room: this.room.id})
				this.server = server
				this.roomId = roomId
				this.token = token
				this.iceServers = iceServers
				this.initJanus()
			} catch (e) {
				this.joinError = e.message
				this.loading = false
			}
		},
		toggleMute () {
			if (this.pluginHandle == null) {
				return
			}
			this.knownMuteState = this.pluginHandle.isAudioMuted()
			if (this.knownMuteState) {
				this.pluginHandle.unmuteAudio()
			} else {
				this.pluginHandle.muteAudio()
			}
			this.knownMuteState = this.pluginHandle.isAudioMuted()
		},
		attachToRoom () {
			// Roughly based on https://janus.conf.meetecho.com/videoroomtest.js
			const comp = this
			this.janus.attach(
				{
					plugin: 'janus.plugin.videoroom',
					opaqueId: this.user.id,
					success: function (pluginHandle) {
						comp.pluginHandle = pluginHandle
						Janus.log(
							'Plugin attached! (' + comp.pluginHandle.getPlugin() + ', id=' + comp.pluginHandle.getId() + ')')

						const register = {
							request: 'join',
							room: comp.roomId,
							ptype: 'publisher',
							token: comp.token,
							display: comp.user.id, // we abuse janus' display name field for the venueless user id
						}
						comp.pluginHandle.send({message: register})
					},
					error: function (error) {
						Janus.error('  -- Error attaching plugin...', error)
						alert('Error attaching plugin... ' + error)
					},
					consentDialog: function (on) {
						Janus.debug('Consent dialog should be ' + (on ? 'on' : 'off') + ' now')
						// TODO
					},
					iceState: function (state) {
						if (state === 'failed') {
							alert('WebRTC connection failed')
						}
						Janus.log('ICE state changed to ' + state)
					},
					mediaState: function (medium, on) {
						Janus.log('Janus ' + (on ? 'started' : 'stopped') + ' receiving our ' + medium)
					},
					webrtcState: function (on) {
						Janus.log('Janus says our WebRTC PeerConnection is ' + (on ? 'up' : 'down') + ' now')
						// if (!on)
						//	return
					},
					onmessage: function (msg, jsep) {
						Janus.debug(' ::: Got a message (publisher) :::', msg)
						var event = msg.videoroom
						Janus.debug('Event: ' + event)
						if (event) {
							if (event === 'joined') {
								// Publisher/manager created, negotiate WebRTC and attach to existing feeds, if any
								comp.ourId = msg.id
								comp.ourPrivateId = msg.private_id
								Janus.log('Successfully joined room ' + msg.room + ' with ID ' + comp.ourId)
								comp.publishOwnFeed(true)
								comp.loading = false
								// Any new feed to attach to?
								if (msg.publishers) {
									var list = msg.publishers
									Janus.debug('Got a list of available publishers/feeds:', list)
									for (const f of list) {
										const id = f.id
										const display = f.display
										const audio = f.audio_codec
										const video = f.video_codec
										Janus.debug('  >> [' + id + '] ' + display + ' (audio: ' + audio + ', video: ' + video + ')')
										comp.newRemoteFeed(id, display, audio, video)
									}
								}
							} else if (event === 'destroyed') {
								// The room has been destroyed
								Janus.warn('The room has been destroyed!')
								alert('The room has been destroyed') // todo
							} else if (event === 'event') {
								// Any new feed to attach to?
								if (msg.publishers) {
									const list = msg.publishers
									Janus.debug('Got a list of available publishers/feeds:', list)
									for (const f of list) {
										const id = f.id
										const display = f.display
										const audio = f.audio_codec
										const video = f.video_codec
										Janus.debug('  >> [' + id + '] ' + display + ' (audio: ' + audio + ', video: ' + video + ')')
										comp.newRemoteFeed(id, display, audio, video)
									}
								} else if (msg.leaving) {
									// One of the publishers has gone away?
									const leaving = msg.leaving
									Janus.log('Publisher left: ' + leaving)
									const remoteFeed = comp.feeds.find((rf) => rf.rfid === leaving)
									if (remoteFeed != null) {
										Janus.debug(
											'Feed ' + remoteFeed.rfid + ' (' + remoteFeed.rfdisplay + ') has left the room, detaching')
										comp.feeds = comp.feeds.filter((rf) => rf.rfid !== remoteFeed.rfid)
										remoteFeed.detach()
									}
								} else if (msg.unpublished) {
									// One of the publishers has unpublished?
									const unpublished = msg.unpublished
									Janus.log('Publisher left: ' + unpublished)
									if (unpublished === 'ok') {
										// That's us
										comp.pluginHandle.hangup()
										return
									}
									const remoteFeed = comp.feeds.find((rf) => rf.rfid === unpublished)
									if (remoteFeed != null) {
										Janus.debug(
											'Feed ' + remoteFeed.rfid + ' (' + remoteFeed.rfdisplay + ') has left the room, detaching')
										comp.feeds = comp.feeds.filter((rf) => rf.rfid !== remoteFeed.rfid)
										remoteFeed.detach()
									}
								} else if (msg.error) {
									if (msg.error_code === 426) {
										// This is a "no such room" error: give a more meaningful description
										// todo
										alert('Room does not exist')
									} else {
										alert(msg.error) // todo
									}
								}
							}
						}
						if (jsep) {
							Janus.debug('Handling SDP as well...', jsep)
							comp.pluginHandle.handleRemoteJsep({jsep: jsep})
							// Check if any of the media we wanted to publish has
							// been rejected (e.g., wrong or unsupported codec)
							var audio = msg.audio_codec
							if (comp.ourStream && comp.ourStream.getAudioTracks() && comp.ourStream.getAudioTracks().length > 0 &&
								!audio) {
								// Audio has been rejected
								console.warning('Our audio stream has been rejected, viewers won\'t hear us')
							}
							var video = msg.video_codec
							if (comp.ourStream && comp.ourStream.getVideoTracks() && comp.ourStream.getVideoTracks().length > 0 &&
								!video) {
								// Video has been rejected
								console.warning('Our video stream has been rejected, viewers won\'t see us')
								comp.ourVideoVisible = false
								// todo: Hide the webcam video
							}
						}
					},
					onlocalstream: function (stream) {
						Janus.debug(' ::: Got a local stream :::', stream)
						this.ourStream = stream
						// todo: show local stream
						// Janus.attachMediaStream($('#myvideo').get(0), stream)
						// $('#myvideo').get(0).muted = 'muted'
						if (comp.pluginHandle.webrtcStuff.pc.iceConnectionState !== 'completed' &&
							comp.pluginHandle.webrtcStuff.pc.iceConnectionState !== 'connected') {
							// todo show that we are still publishing…
						}
						const videoTracks = stream.getVideoTracks()
						if (!videoTracks || videoTracks.length === 0) {
							// No webcam
							// todo: no webcam found
							comp.ourVideoVisible = false
						} else {
							comp.ourVideoVisible = true
							Janus.attachMediaStream(comp.$refs.ourVideo, stream)
							comp.$refs.ourVideo.muted = 'muted'
							comp.knownMuteState = comp.pluginHandle.isAudioMuted()
						}
					},
					onremotestream: function (stream) {
						// The publisher stream is sendonly, we don't expect anything here
					},
					oncleanup: function () {
						Janus.log(' ::: Got a cleanup notification: we are unpublished now :::')
						this.ourStream = null
					},
				})
		},
		publishOwnFeed (useAudio) {
			const comp = this
			const media = {audioRecv: false, videoRecv: false, audioSend: useAudio, videoSend: true}	// Publishers are sendonly
			if (localStorage.audioInput) {
				media.audio = {deviceId: localStorage.audioInput}
			}
			if (localStorage.audioInput !== this.audioInput) {
				media.replaceAudio = true
				this.audioInput = localStorage.audioInput
			}
			if (localStorage.videoInput) {
				media.video = {deviceId: localStorage.videoInput}
			}
			if (localStorage.videoInput !== this.videoInput) {
				media.replaceVideo = true
				this.videoInput = localStorage.videoInput
			}

			this.pluginHandle.createOffer(
				{
					media: media,
					// If you want to test simulcasting (Chrome and Firefox only), set to true
					simulcast: false,
					simulcast2: false,
					success: function (jsep) {
						Janus.debug('Got publisher SDP!', jsep)
						var publish = {request: 'configure', audio: useAudio, video: true}
						// You can force a specific codec to use when publishing by using the
						// audiocodec and videocodec properties, for instance:
						// 		publish["audiocodec"] = "opus"
						// to force Opus as the audio codec to use, or:
						// 		publish["videocodec"] = "vp9"
						// to force VP9 as the videocodec to use. In both case, though, forcing
						// a codec will only work if: (1) the codec is actually in the SDP (and
						// so the browser supports it), and (2) the codec is in the list of
						// allowed codecs in a room. With respect to the point (2) above,
						// refer to the text in janus.plugin.videoroom.jcfg for more details
						comp.pluginHandle.send({message: publish, jsep: jsep})
					},
					error: function (error) {
						Janus.error('WebRTC error:', error)
						if (useAudio) {
							comp.publishOwnFeed(false)
						} else {
							alert('WebRTC error... ' + error.message)
						}
					},
				})
		},
		newRemoteFeed (id, display, audio, video) {
			// A new feed has been published, create a new plugin handle and attach to it as a subscriber
			let remoteFeed = null
			const comp = this
			this.janus.attach({
				plugin: 'janus.plugin.videoroom',
				opaqueId: this.user.id,
				success: function (pluginHandle) {
					remoteFeed = pluginHandle
					remoteFeed.simulcastStarted = false
					Janus.log('Plugin attached! (' + remoteFeed.getPlugin() + ', id=' + remoteFeed.getId() + ')')
					Janus.log('  -- This is a subscriber')
					// We wait for the plugin to send us an offer
					var subscribe = {
						request: 'join',
						room: comp.roomId,
						ptype: 'subscriber',
						feed: id,
						private_id: comp.ourPrivateId,
					}
					// In case you don't want to receive audio, video or data, even if the
					// publisher is sending them, set the 'offer_audio', 'offer_video' or
					// 'offer_data' properties to false (they're true by default), e.g.:
					// 		subscribe["offer_video"] = false
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
				error: function (error) {
					Janus.error('  -- Error attaching plugin...', error)
					alert('Error attaching plugin... ' + error)
				},
				onmessage: function (msg, jsep) {
					Janus.debug(' ::: Got a message (subscriber) :::', msg)
					var event = msg.videoroom
					Janus.debug('Event: ' + event)
					if (msg.error) {
						alert(msg.error)
					} else if (event) {
						if (event === 'attached') {
							// Subscriber created and attached
							remoteFeed.rfattached = false
							remoteFeed.rfid = msg.id
							remoteFeed.venueless_user_id = msg.display
							remoteFeed.venueless_user = null
							comp.feeds.push(remoteFeed)
							comp.fetchUser(remoteFeed)
							// todo: show spinner?
							Janus.log(
								'Successfully attached to feed ' + remoteFeed.rfid + ' (' + remoteFeed.venueless_user_id + ') in room ' +
								msg.room)
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
							success: function (jsep) {
								Janus.debug('Got SDP!', jsep)
								var body = {request: 'start', room: comp.roomId}
								remoteFeed.send({message: body, jsep: jsep})
							},
							error: function (error) {
								Janus.error('WebRTC error:', error)
								alert('WebRTC error... ' + error.message)
							},
						})
					}
				},
				iceState: function (state) {
					Janus.log(
						'ICE state of this WebRTC PeerConnection (feed #' + remoteFeed.rfid + ') changed to ' + state)
				},
				webrtcState: function (on) {
					Janus.log(
						'Janus says this WebRTC PeerConnection (feed #' + remoteFeed.rfid + ') is ' + (on ? 'up' : 'down') +
						' now')
				},
				onlocalstream: function (stream) {
					// The subscriber stream is recvonly, we don't expect anything here
				},
				onremotestream: function (stream) {
					Janus.debug('Remote feed #' + remoteFeed.rfid + ', stream:', stream)
					const rfindex = comp.feeds.findIndex((rf) => rf.rfid === remoteFeed.rfid)
					if (!remoteFeed.rfattached) {
						remoteFeed.rfattached = true
					}
					// todo: Show spinner until `playing` event on video
					Janus.attachMediaStream(comp.$refs.peerVideo[rfindex], stream)
					if (localStorage.audioOutput) {
						if (comp.$refs.peerVideo[rfindex].setSinkId) { // chrome only for now
							comp.$refs.peerVideo[rfindex].setSinkId(localStorage.audioOutput)
						}
					}
					var videoTracks = stream.getVideoTracks()
					if (!videoTracks || videoTracks.length === 0) {
						// todo: indicate that no remote video
					} else {
						// todo: show remote video only now?
					}
				},
				oncleanup: function () {
					Janus.log(' ::: Got a cleanup notification (remote feed ' + id + ') :::')
					// handled further above
				},
			})
		},
		connectToServer () {
			this.janus = new Janus({
				server: this.server,
				iceServers: this.iceServers,
				success: this.attachToRoom,
				error (error) {
					Janus.error(error)
					alert(error)
					// todo: handle
				},
				destroyed () {
					// todo: handle?
				},
			})
		},
		async fetchUser (feed) {
			this.$set(feed, 'venueless_user', await api.call('user.fetch', {id: feed.venueless_user_id}))
		},
		initJanus () {
			Janus.init({
				debug: 'all', // todo: conditional
				callback: this.connectToServer,
			})
		},
	},
}
</script>
<style lang="stylus">
	.c-roulette
		flex: auto
		height: auto // 100% breaks safari
		display: flex
		flex-direction: column
		position: relative

		.users
			display: flex
			height: auto // 100% breaks safari
			flex: auto
			flex-direction: row
			max-height: 100%

		.users > div
			background: #000
			flex: auto
			width: 100%
			height: 100%
			max-height: 100%
			position: relative
			overflow: hidden

			.user
				cursor: pointer
				.display-name
					margin-left: 8px
					flex: auto
					ellipsis()

			.user, .controls
				display: flex
				align-items: center
				padding: 0 15px
				min-height: 48px
				position: absolute
				top: 10px
				left: 50%
				transform: translate(-50%)
				opacity: 0
				transition: opacity .5s
				card()

			&:hover .user, &:hover .controls, .controls.always
				transition: opacity .5s
				opacity: 1

			video
				// this positioning is basically background-size: cover
				left: 50%
				min-height: 100%
				min-width: 100%
				position: absolute
				top: 50%
				transform: translate(-50%, -50%)

		.users > .no-peer
			background: white
			display: flex
			align-items: center
			justify-content: center
			flex-direction: column

		.users > .me
			background: white
			display: flex
			align-items: center
			justify-content: center
			flex-direction: column
			video
				transform: translate(-50%, -50%) rotateY(180deg)

	.next
		position: absolute
		bottom: 10px
		left: 50%
		transform: translate(-50%, -50%)
		.btn-next
			themed-button-primary(size: large)
</style>

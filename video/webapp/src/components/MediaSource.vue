<template lang="pug">
.c-media-source(:class="{'in-background': background, 'in-room-manager': inRoomManager}")
	transition(name="background-room")
		router-link.background-room(v-if="background", :to="room ? {name: 'room', params: {roomId: room.id}}: {name: 'channel', params: {channelId: call.channel}}")
			.description
				.hint {{ $t('MediaSource:room:hint') }}
				.room-name(v-if="room") {{ room.name }}
				.room-name(v-else="call") {{ $t('MediaSource:call:label') }}
			.global-placeholder
			bunt-icon-button(@click.prevent.stop="$emit('close')") close
	livestream(v-if="room && module.type === 'livestream.native'", ref="livestream", :room="room", :module="module", :size="background ? 'tiny' : 'normal'", :key="`livestream-${room.id}`")
	janus-call(v-else-if="room && module.type === 'call.janus'", ref="janus", :room="room", :module="module", :background="background", :size="background ? 'tiny' : 'normal'", :key="`janus-${room.id}`")
	janus-channel-call(v-else-if="call", ref="janus", :call="call", :background="background", :size="background ? 'tiny' : 'normal'", :key="`call-${call.id}`", @close="$emit('close')")
	.iframe-error(v-if="iframeError") {{ $t('MediaSource:iframe-error:text') }}
</template>
<script>
// TODO functional component?
import api from 'lib/api'
import JanusCall from 'components/JanusCall'
import JanusChannelCall from 'components/JanusChannelCall'
import Livestream from 'components/Livestream'

export default {
	components: { Livestream, JanusCall, JanusChannelCall },
	props: {
		room: Object,
		call: Object,
		background: {
			type: Boolean,
			default: false
		}
	},
	data () {
		return {
			iframeError: null
		}
	},
	computed: {
		module () {
			return this.room.modules.find(module => ['livestream.native', 'livestream.youtube', 'livestream.iframe', 'call.bigbluebutton', 'call.janus', 'call.zoom'].includes(module.type))
		},
		inRoomManager () {
			return this.$route.name === 'room:manage'
		}
	},
	watch: {
		background () {
			if (!this.iframe) return
			if (this.background) {
				this.iframe.classList.add('background')
			} else {
				this.iframe.classList.remove('background')
			}
		}
	},
	async mounted () {
		if (this.room) api.call('room.enter', {room: this.room.id})
		try {
			let iframeUrl
			let hideIfBackground = false
			switch (this.module.type) {
				case 'call.bigbluebutton': {
					({url: iframeUrl} = await api.call('bbb.room_url', {room: this.room.id}))
					hideIfBackground = true
					break
				}
				case 'call.zoom': {
					({url: iframeUrl} = await api.call('zoom.room_url', {room: this.room.id}))
					hideIfBackground = true
					break
				}
				case 'livestream.iframe': {
					iframeUrl = this.module.config.url
					break
				}
				case 'livestream.youtube': {
					iframeUrl = `https://www.youtube-nocookie.com/embed/${this.module.config.ytid}?autoplay=1&rel=0&showinfo=0`
					break
				}
			}
			if (!iframeUrl || !this.$el || this._isDestroyed) return
			const iframe = document.createElement('iframe')
			iframe.src = iframeUrl
			iframe.classList.add('iframe-media-source')
			if (hideIfBackground) {
				iframe.classList.add('hide-if-background')
			}
			iframe.allow = 'camera; autoplay; microphone; fullscreen; display-capture'
			iframe.allowfullscreen = true
			iframe.allowusermedia = true
			iframe.setAttribute('allowfullscreen', '') // iframe.allowfullscreen is not enough in firefox#media-source-iframes
			const container = document.querySelector('#media-source-iframes')
			container.appendChild(iframe)
			this.iframe = iframe
		} catch (error) {
			// TODO handle bbb/zoom.join.missing_profile
			this.iframeError = error
			console.log(error)
		}
	},
	beforeDestroy () {
		this.iframe?.remove()
		if (api.socketState !== 'open') return
		if (this.room) api.call('room.leave', {room: this.room.id})
	},
	methods: {
		isPlaying () {
			if (this.call) {
				return this.$refs.janus.roomId
			}
			if (this.module.type === 'livestream.native') {
				return this.$refs.livestream.playing && !this.$refs.livestream.offline
			}
			if (this.module.type === 'call.janus') {
				return this.$refs.janus.roomId
			}
			if (this.module.type === 'call.bigbluebutton') {
				return !!this.iframe
			}
			if (this.module.type === 'call.zoom') {
				return !!this.iframe
			}
			return true
		}
	}
}
</script>
<style lang="stylus">
.c-media-source
	position: absolute
	width: 0
	height: 0
	&.in-background
		z-index: 101
	.background-room
		position: fixed
		top: 3px
		right: 4px
		card()
		display: flex
		align-items: center
		height: 48px
		min-width: 280px
		max-width: 380px
		.description
			flex: auto
			align-self: stretch
			padding: 4px 8px
			max-width: 238px
			.hint
				color: $clr-secondary-text-light
				font-size: 10px
				margin-bottom: 2px
			.room-name
				color: var(--clr-text-primary)
				font-weight: 500
				flex-grow: 0
				ellipsis()
		.global-placeholder
			width: 86px
			flex: none
		.bunt-icon-button
			icon-button-style(style: clear)
			margin: 0 2px
		+below('l')
			top: 51px
	.background-room-enter-active, .background-room-leave-active
		transition: transform .3s ease
	// .background-room-enter-active
	// 	transition-delay: .1s
	.background-room-enter, .background-room-leave-to
		transform: translate(calc(-1 * var(--chatbar-width)), 52px)
.c-media-source .c-livestream, .c-media-source .c-januscall, .c-media-source .c-januschannelcall, iframe.iframe-media-source
	position: fixed
	transition: all .3s ease
	&.size-tiny, &.background
		bottom: calc(var(--vh100) - 48px - 3px)
		right: 4px + 36px + 4px
		+below('l')
			bottom: calc(var(--vh100) - 48px - 48px - 3px)
	&:not(.size-tiny):not(.background)
		bottom: calc(var(--vh100) - 56px - var(--mediasource-placeholder-height))
		right: calc(100vw - var(--sidebar-width) - var(--mediasource-placeholder-width))
		width: var(--mediasource-placeholder-width)
		height: var(--mediasource-placeholder-height)
		+below('l')
			bottom: calc(var(--vh100) - 48px - 56px - var(--mediasource-placeholder-height))
			right: calc(100vw - var(--mediasource-placeholder-width))
		+below('m')
			bottom: calc(var(--vh100) - 48px - 56px - var(--mobile-media-height))
			right: 0
			width: 100vw
			height: var(--mobile-media-height)
iframe.iframe-media-source
	transition: all .3s ease
	border: none
	&.background
		pointer-events: none
		height: 48px
		width: 86px
		z-index: 101
		&.hide-if-background
			width: 0
			height: 0
</style>

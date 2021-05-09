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
	you-tube(v-else-if="room && module.type === 'livestream.youtube'", ref="youtube", :room="room", :module="module", :size="background ? 'tiny' : 'normal'", :key="`youtube-${room.id}`")
	big-blue-button(v-else-if="room && module.type === 'call.bigbluebutton'", ref="bigbluebutton", :room="room", :module="module", :background="background", :key="`bbb-${room.id}`")
	zoom(v-else-if="room && module.type === 'call.zoom'", ref="zoom", :room="room", :module="module", :background="background", :key="`zoom-${room.id}`")
	janus-call(v-else-if="room && module.type === 'call.janus'", ref="janus", :room="room", :module="module", :background="background", :size="background ? 'tiny' : 'normal'", :key="`janus-${room.id}`")
	janus-channel-call(v-else-if="call", ref="janus", :call="call", :background="background", :size="background ? 'tiny' : 'normal'", :key="`call-${call.id}`", @close="$emit('close')")
</template>
<script>
// TODO functional component?
import api from 'lib/api'
import BigBlueButton from 'components/BigBlueButton'
import Zoom from 'components/Zoom'
import JanusCall from 'components/JanusCall'
import JanusChannelCall from 'components/JanusChannelCall'
import Livestream from 'components/Livestream'
import YouTube from 'components/YouTube'

export default {
	components: { BigBlueButton, Zoom, Livestream, YouTube, JanusCall, JanusChannelCall },
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
		}
	},
	computed: {
		module () {
			return this.room.modules.find(module => ['livestream.native', 'livestream.youtube', 'call.bigbluebutton', 'call.janus', 'call.zoom'].includes(module.type))
		},
		inRoomManager () {
			return this.$route.name === 'room:manage'
		}
	},
	created () {
		if (this.room) api.call('room.enter', {room: this.room.id})
	},
	beforeDestroy () {
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
			if (this.module.type === 'livestream.youtube') {
				return true
			}
			if (this.module.type === 'call.janus') {
				return this.$refs.janus.roomId
			}
			if (this.module.type === 'call.bigbluebutton') {
				return !!this.$refs.bigbluebutton.iframe
			}
			if (this.module.type === 'call.zoom') {
				return !!this.$refs.zoom.iframe
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
	.c-livestream, .c-youtube, .c-januscall, .c-bigbluebutton, .c-zoom, .c-januschannelcall
		position: fixed
		transition: all .3s ease
		&.size-tiny
			bottom: calc(var(--vh100) - 48px - 3px)
			right: 4px + 36px + 4px
			+below('l')
				bottom: calc(var(--vh100) - 48px - 48px - 3px)
		&:not(.size-tiny)
			bottom: calc(56px * var(--has-stagetools))
			right: var(--chatbar-width)
			width: calc(100vw - var(--sidebar-width) - var(--chatbar-width))
			height: calc(var(--vh100) - 56px * (1 + var(--has-stagetools)))
			+below('l')
				height: calc(var(--vh100) - 56px * (1 + var(--has-stagetools)) - 48px)
				width: calc(100vw - var(--chatbar-width))
			+below('m')
				bottom: calc(var(--vh100) - 48px - 56px - var(--mobile-media-height))
				right: 0
				width: 100vw
				height: var(--mobile-media-height)
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
	&.in-room-manager
		.c-livestream, .c-youtube
			bottom: calc(var(--vh100) - 56px - 360px)
			right: calc(var(--chatbar-width) * 3 + 3px)
			width: calc(100vw - var(--sidebar-width) - var(--chatbar-width) * 3 - 3px)
			height: 360px
</style>

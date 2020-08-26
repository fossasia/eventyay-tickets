<template lang="pug">
.c-media-source
	transition(name="background-room")
		.background-room(v-if="background")
			.description
				.hint {{ $t('MediaSource:room:hint') }}
				.room-name {{ room.name }}
			.global-placeholder
			bunt-icon-button(@click="$emit('close')") close
	livestream(v-if="module.type === 'livestream.native'", ref="livestream", :room="room", :module="module", :size="background ? 'tiny' : 'normal'", :key="room.id")
	big-blue-button(v-else-if="module.type === 'call.bigbluebutton'", ref="bigbluebutton", :room="room", :module="module", :background="background", :key="room.id")
</template>
<script>
// TODO functional component?
import api from 'lib/api'
import BigBlueButton from 'components/BigBlueButton'
import Livestream from 'components/Livestream'

export default {
	components: { BigBlueButton, Livestream },
	props: {
		room: Object,
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
			return this.room.modules.find(module => ['livestream.native', 'call.bigbluebutton'].includes(module.type))
		},
	},
	created () {
		api.call('room.enter', {room: this.room.id})
	},
	beforeDestroy () {
		if (api.socketState !== 'open') return
		api.call('room.leave', {room: this.room.id})
	},
	methods: {
		isPlaying () {
			if (this.module.type === 'livestream.native') {
				return this.$refs.livestream.playing
			}
			if (this.module.type === 'call.bigbluebutton') {
				return !!this.$refs.bigbluebutton.iframe
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
	.c-livestream
		position: fixed
		transition: all .3s ease
		&.size-tiny
			bottom: calc(var(--vh100) - 48px - 3px)
			right: 4px + 36px + 4px
			+below('l')
				bottom: calc(var(--vh100) - 48px - 48px - 3px)
		&:not(.size-tiny)
			bottom: 56px
			right: var(--chatbar-width)
			width: calc(100vw - var(--sidebar-width) - var(--chatbar-width))
			height: calc(var(--vh100) - 56px * 2)
			+below('l')
				height: calc(var(--vh100) - 56px * 2 - 48px)
				width: calc(100vw - var(--chatbar-width))
			+below('m')
				bottom: calc(var(--vh100) - 48px - 56px - 40vh)
				right: 0
				width: 100vw
				height: 40vh
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
</style>

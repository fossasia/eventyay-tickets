<template lang="pug">
.c-bigbluebutton(:class="{background}")
	.error(v-if="error") {{ $t('BigBlueButton:error:text') }}
</template>
<script>
import api from 'lib/api'
export default {
	props: {
		room: {
			type: Object,
			required: true
		},
		module: {
			type: Object,
			required: true
		},
		background: Boolean
	},
	data () {
		return {
			error: null
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
	destroyed () {
		this.iframe?.remove()
	},
	async created () {
		try {
			const {url} = await api.call('bbb.room_url', {room: this.room.id})
			const iframe = document.createElement('iframe')
			iframe.src = url
			iframe.classList.add('bigbluebutton')
			iframe.allow = 'camera; autoplay; microphone; fullscreen; display-capture'
			iframe.allowfullscreen = true
			iframe.allowusermedia = true
			const app = document.querySelector('#app')
			app.appendChild(iframe)
			this.iframe = iframe
		} catch (error) {
			// TODO handle bbb.join.missing_profile
			this.error = error
			console.log(error)
		}
	}
}
</script>
<style lang="stylus">
.c-bigbluebutton
	flex: auto
	height: 100%
	display: flex
	flex-direction: column
	align-items: center
	justify-content: center
	position: fixed
	bottom: 0
	right: 0
	width: calc(100vw - var(--sidebar-width))
	height: calc(var(--vh100) - 56px)
	&.background
		pointer-events: none
		width: 0
		height: 0
iframe.bigbluebutton
	position: fixed
	bottom: 0
	right: 0
	width: calc(100vw - var(--sidebar-width))
	height: calc(var(--vh100) - 56px)
	border: none
	transition: all .3s ease
	&.background
		height: 0
		width: 0
		pointer-events: none
		bottom: calc(var(--vh100) - 48px - 3px)
		right: 4px + 36px + 4px
	+below('l')
		width: 100vw
		height: calc(var(--vh100) - 56px - 48px)
</style>

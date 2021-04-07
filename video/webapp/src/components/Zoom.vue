<template lang="pug">
.c-zoom(:class="{background}")
	.error(v-if="error") {{ $t('Zoom:error:text') }}
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
			const {url} = await api.call('zoom.room_url', {room: this.room.id})
			if (!this.$el || this._isDestroyed) return
			const iframe = document.createElement('iframe')
			iframe.src = url
			iframe.classList.add('zoom')
			iframe.allow = 'camera; autoplay; microphone; fullscreen; display-capture'
			iframe.allowfullscreen = true
			iframe.allowusermedia = true
			iframe.setAttribute('allowfullscreen', '') // iframe.allowfullscreen is not enough in firefox
			const app = document.querySelector('#app')
			app.appendChild(iframe)
			this.iframe = iframe
		} catch (error) {
			// TODO handle zoom.join.missing_profile
			this.error = error
			console.log(error)
		}
	}
}
</script>
<style lang="stylus">
.c-zoom
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
iframe.zoom
	position: fixed
	bottom: 0
	right: var(--chatbar-width)
	width: calc(100vw - var(--sidebar-width) - var(--chatbar-width))
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
		height: calc(var(--vh100) - 56px - 48px)
		width: calc(100vw - var(--chatbar-width))
	+below('m')
		bottom: calc(var(--vh100) - 48px - 56px - var(--mobile-media-height))
		right: 0
		width: 100vw
		height: var(--mobile-media-height)
</style>

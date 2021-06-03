<template lang="pug">
.c-iframe-player(:class="{background}")
</template>
<script>
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
	mounted () {
		if (!this.$el || this._isDestroyed) return
		const iframe = document.createElement('iframe')
		iframe.src = this.module.config.url
		iframe.classList.add('iframeplayer')
		iframe.allow = 'autoplay; fullscreen'
		iframe.allowfullscreen = true
		iframe.setAttribute('allowfullscreen', '') // iframe.allowfullscreen is not enough in firefox
		const app = document.querySelector('#app')
		app.appendChild(iframe)
		this.iframe = iframe
	}
}
</script>
<style lang="stylus">
// TODO unify that copypasta
.c-iframe-player
	flex: auto
	display: flex
	flex-direction: column
	min-height: 0
	height: 100%
	background-color: $clr-black
	position: relative
	overflow: hidden
	&.background
		pointer-events: none
		width: 0
		height: 0
iframe.iframeplayer
	position: fixed
	bottom: calc(56px * var(--has-stagetools))
	right: var(--chatbar-width)
	width: calc(100vw - var(--sidebar-width) - var(--chatbar-width))
	height: calc(var(--vh100) - 56px * (1 + var(--has-stagetools)))
	border: none
	transition: all .3s ease
	&.background
		height: 48px
		width: 86px
		bottom: calc(var(--vh100) - 48px - 3px)
		right: 4px + 36px + 4px
		pointer-events: none
		z-index: 101
		+below('l')
			bottom: calc(var(--vh100) - 48px - 48px - 3px)
	+below('l')
		height: calc(var(--vh100) - 56px * (1 + var(--has-stagetools)) - 48px)
		width: calc(100vw - var(--chatbar-width))
	+below('m')
		bottom: calc(var(--vh100) - 48px - 56px - var(--mobile-media-height))
		right: 0
		width: 100vw
		height: var(--mobile-media-height)
</style>

<template lang="pug">
#presentation-mode(:class="{fullscreen}", :style="[style, themeVariables]")
	.fatal-indicator.mdi.mdi-alert-octagon(v-if="fatalError || fatalConnectionError", :title="errorMessage")
	.content(v-else-if="world")
		router-view(:room="room")
	bunt-progress-circular(v-else, size="small")
</template>
<script>
import { mapState } from 'vuex'
import { themeVariables } from 'theme'
import api from 'lib/api'

const SLIDE_WIDTH = 960
const SLIDE_HEIGHT = 700

export default {
	props: {
		roomId: String
	},
	data () {
		return {
			fullscreen: false,
			themeVariables,
			scale: 1
		}
	},
	computed: {
		...mapState(['fatalConnectionError', 'fatalError', 'connected', 'world', 'rooms']),
		errorMessage () {
			return this.fatalConnectionError?.code || this.fatalError?.message
		},
		room () {
			return this.rooms?.find(room => room.id === this.$route.params.roomId) || this.rooms?.[0]
		},
		style () {
			return {
				'--scale': this.scale.toFixed(1)
			}
		}
	},
	watch: {
		room () {
			this.$store.dispatch('changeRoom', this.room)
			api.call('room.enter', {room: this.room.id})
		}
	},
	created () {
		this.fullscreen = this.$route.query.fullscreen ?? !this.$route.name.endsWith('chat')
	},
	mounted () {
		window.addEventListener('resize', this.computeScale)
		this.computeScale()
	},
	beforeDestroy () {
		window.removeEventListener('resize', this.computeScale)
	},
	methods: {
		computeScale () {
			if (!this.fullscreen) return
			const width = document.body.offsetWidth
			const height = document.body.offsetHeight
			this.scale = Math.min(width / SLIDE_WIDTH, height / SLIDE_HEIGHT)
		}
	}
}
</script>
<style lang="stylus">
#presentation-mode
	height: 100%
	display: flex
	flex-direction: column
	font-size: 16px // somehow obs has no default font size, so setting size via percentage breaks everything
	> .bunt-progress-circular, > .fatal-indicator
		position: fixed
		top: 100%
		left: 0
		transform: translate(4px, calc(-100% - 4px))
	> .fatal-indicator
		color: $clr-danger
		font-size: 1vw

	> .content
		display: flex
		flex-direction: column
		transform: scale(var(--scale)) translateZ(0)
		height: 100vh
	&.fullscreen
		justify-content: center
		align-items: center
		> .content

			justify-content: center
			align-items: center
			width: 960px
			height: 700px
			flex: none
</style>

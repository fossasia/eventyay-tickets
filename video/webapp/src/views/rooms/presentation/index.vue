<template lang="pug">
#presentation-mode(:style="[style, themeVariables]")
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
		roomId: String,
		type: String
	},
	data () {
		return {
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
	mounted () {
		window.addEventListener('resize', this.computeScale)
		this.computeScale()
	},
	beforeDestroy () {
		window.removeEventListener('resize', this.computeScale)
	},
	methods: {
		computeScale () {
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
	justify-content: center
	align-items: center
	font-size: 14px // somehow obs has no default font size, so setting size via percentage breaks everything
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
		justify-content: center
		align-items: center
		width: 960px
		height: 700px
		flex: none
		transform: scale(var(--scale)) translateZ(0)
</style>

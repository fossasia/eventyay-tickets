<template lang="pug">
#standalone-app(:class="{fullscreen, 'themed-bg': themedBackground}", :style="[style, themeVariables]")
	.fatal-indicator.mdi.mdi-alert-octagon(v-if="fatalError || fatalConnectionError", :title="errorMessage")
	.content(v-else-if="world")
		router-view(:room="room", :config="config")
	bunt-progress-circular(v-else, size="small")
	//- hoist reactions to escale scaling
	ReactionsOverlay(v-if="$route.name === 'standalone:kiosk' && config.show_reactions")
</template>
<script>
// TODO
// - logo
// - sponsor bar
import { mapState } from 'vuex'
import { themeVariables, computeForegroundColor } from 'theme'
import ReactionsOverlay from 'components/ReactionsOverlay.vue'

const SLIDE_WIDTH = 960
const SLIDE_HEIGHT = 700

export default {
	components: { ReactionsOverlay },
	props: {
		roomId: String
	},
	data () {
		return {
			fullscreen: false,
			themedBackground: true,
			themeVariables,
			scale: 1
		}
	},
	computed: {
		...mapState(['fatalConnectionError', 'fatalError', 'connected', 'user', 'world', 'rooms']),
		errorMessage () {
			return this.fatalConnectionError?.code || this.fatalError?.message
		},
		room () {
			return this.rooms?.find(room => room.id === this.$route.params.roomId) || this.rooms?.[0]
		},
		config () {
			return this.user?.profile ?? {}
		},
		style () {
			return {
				'--scale': this.scale.toFixed(1),
				'--clr-standalone-bg': this.config.background_color ?? 'var(--clr-primary)',
				'--clr-standalone-fg': this.config.background_color ? computeForegroundColor(this.config.background_color) : 'var(--clr-input-primary-fg)'
			}
		}
	},
	watch: {
		room () {
			this.$store.dispatch('changeRoom', this.room)
		}
	},
	created () {
		this.$store.dispatch('changeRoom', this.room)
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
			this.$store.commit('reportMediaSourcePlaceholderRect', this.$el.getBoundingClientRect())
		}
	}
}
</script>
<style lang="stylus">
#standalone-app
	height: 100%
	display: flex
	flex-direction: column
	font-size: 16px // somehow obs has no default font size, so setting size via percentage breaks everything
	--mediasource-placeholder-height: 100vh
	--mediasource-placeholder-width: 100vw
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
	&.themed-bg
		background-color: var(--clr-standalone-bg)
		color: var(--clr-standalone-fg)
	.c-reactions-overlay
		bottom: 0
		right: 0
		.reaction
			height: calc(28px * var(--scale))
			width: @height
			bottom: calc(-32px * var(--scale))
</style>

<template lang="pug">
.c-reactions-overlay(v-resize-observer="onResize")
</template>
<script>
import { mapState } from 'vuex'
import shuffle from 'lodash/shuffle'
import emojiData from 'emoji-mart/data/twitter.json'
import { getEmojiPosition } from 'lib/emoji'

const MAX_PARTICLE_POOL = 70 // TODO derive from width to have consistent density
const SERVER_REACTIONS_INTERVAL = 1000

export default {
	props: {
		showReactionBar: Boolean
	},
	components: {},
	data () {
		return {
			particlePool: [],
			freeParticles: [],
			overlayHeight: null
		}
	},
	computed: {
		...mapState(['reactions']),
	},
	watch: {
		reactions () {
			// put all reactions in a queue and randomize to get rough averages toghether with the particle pool
			// cap at MAX_PARTICLE_POOL and round up
			let reactions = []
			const totalReactions = Object.values(this.reactions).reduce((acc, count) => acc + count, 0)
			const reactionMultiplier = Math.min(1, MAX_PARTICLE_POOL / totalReactions)
			for (const [reaction, count] of Object.entries(this.reactions)) {
				reactions.push(...Array(Math.ceil(count * reactionMultiplier)).fill(reaction))
			}
			reactions = shuffle(reactions)
			const finalLength = reactions.length
			const distribute = () => {
				if (reactions.length === 0) return
				this.renderReaction(reactions.pop())
				setTimeout(distribute, SERVER_REACTIONS_INTERVAL / finalLength)
			}
			distribute()
		}
	},
	mounted () {
		this.overlayHeight = this.$el.offsetHeight
	},
	methods: {
		renderReaction (id) {
			let element = this.freeParticles.pop()
			if (!element) {
				if (this.particlePool.length < MAX_PARTICLE_POOL) {
					element = document.createElement('div')
					element.classList.add('reaction')
					this.$el.appendChild(element)
					this.particlePool.push(element)
				} else {
					return
				}
			}

			const emoji = emojiData.emojis[id]
			const startingPosition = Math.random()
			const targetHeight = 0.5 * Math.max(0.7, Math.random()) * this.overlayHeight
			element.style['background-position'] = getEmojiPosition(emoji)
			element.style.left = `calc(${startingPosition * 100}% - 24px)`
			const animation = element.animate([
				{opacity: 0, transform: `translateY(-${targetHeight}px)`}
			], {
				duration: 1200 + 500 * Math.random()
			})
			animation.onfinish = () => {
				// onfinish seems to get called twice sometimes?
				if (this.freeParticles.includes(element)) return
				this.freeParticles.push(element)
			}
		},
		onResize () {
			// TODO use reported size from observer
			this.overlayHeight = this.$el.offsetHeight
		}
	}
}
</script>
<style lang="stylus">
.c-reactions-overlay
	position: absolute
	bottom: 56px
	right: var(--chatbar-width)
	width: calc(100vw - var(--sidebar-width) - var(--chatbar-width))
	height: calc(100vh - 112px)
	pointer-events: none
	overflow: hidden
	z-index: 4500
	.reaction
		position: absolute
		bottom: -32px
		height: 28px
		width: @height
		display: inline-block
		background-image: url("~emoji-datasource-twitter/img/twitter/sheets-256/64.png")
		background-size: 5700% 5700%
</style>

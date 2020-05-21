<template lang="pug">
.c-reactions(v-resize-observer="onResize")
	.reactions-overlay(ref="reactions")
	.actions
		bunt-icon-button(v-for="reaction of availableReactions", @click="react(reaction.id)")
			.emoji(:style="reaction.style")
</template>
<script>
import { mapState } from 'vuex'
import shuffle from 'lodash/shuffle'
import emojiData from 'emoji-mart/data/twitter.json'
import { getEmojiPosition } from 'lib/emoji'

const MAX_PARTICLE_POOL = 70 // TODO derive from width to have consistent density
const SERVER_REACTIONS_INTERVAL = 1000

export default {
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
		availableReactions () {
			const emoji = [
				emojiData.emojis['+1'],
				emojiData.emojis.clap,
				emojiData.emojis.heart,
				emojiData.emojis.open_mouth,
			]
			return emoji.map(e => ({id: e.short_names[0], style: {'background-position': getEmojiPosition(e)}}))
		}
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
		this.overlayHeight = this.$refs.reactions.offsetHeight
	},
	methods: {
		react (id) {
			this.$store.dispatch('addReaction', id)
			// TODO display immediately and add own cooldown
		},
		renderReaction (id) {
			let element = this.freeParticles.pop()
			if (!element) {
				if (this.particlePool.length < MAX_PARTICLE_POOL) {
					element = document.createElement('div')
					element.classList.add('reaction', 'emoji')
					this.$refs.reactions.appendChild(element)
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
			this.overlayHeight = this.$refs.reactions.offsetHeight
		}
	}
}
</script>
<style lang="stylus">
.c-reactions
	position: absolute
	bottom: 0
	right: var(--chatbar-width)
	width: calc(100vw - var(--sidebar-width) - var(--chatbar-width))
	height: calc(100vh - 112px)
	pointer-events: none
	z-index: 600
	display: flex
	flex-direction: column
	align-items: center
	justify-content: flex-end
	.actions
		display: flex
		pointer-events: all
		margin-bottom: 24px
		background-color: $clr-white
		border-radius: 24px
		padding: 4px
		z-index: 602
		.bunt-icon-button
			&:not(:first-child)
				margin-left: 8px
	.emoji
		height: 28px
		width: @height
		display: inline-block
		background-image: url("~emoji-datasource-twitter/img/twitter/sheets-256/64.png")
		background-size: 5700% 5700%
	.reactions-overlay
		position: absolute
		top: 0
		left: 0
		width: 100%
		height: 100%
		overflow: hidden
		.reaction
			position: absolute
			bottom: -32px
</style>

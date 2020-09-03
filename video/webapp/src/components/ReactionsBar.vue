<template lang="pug">
.c-reactions-bar(:class="{expanded}")
	.actions(@click="expand")
		bunt-icon-button(v-for="reaction of availableReactions", @click.stop="react(reaction.id)")
			.emoji(:style="reaction.style")
</template>
<script>
import emojiData from 'emoji-mart/data/twitter.json'
import { getEmojiPosition } from 'lib/emoji'

export default {
	props: {
		expanded: Boolean
	},
	data () {
		return {
			particlePool: [],
			freeParticles: [],
			overlayHeight: null
		}
	},
	computed: {
		availableReactions () {
			const emoji = [
				emojiData.emojis.clap,
				emojiData.emojis.heart,
				emojiData.emojis['+1'],
				emojiData.emojis.rolling_on_the_floor_laughing,
				emojiData.emojis.open_mouth,
			]
			return emoji.map(e => ({id: e.short_names[0], style: {'background-position': getEmojiPosition(e)}}))
		}
	},
	methods: {
		expand () {
			if (this.expanded) return
			this.$emit('expand')
		},
		react (id) {
			this.$store.dispatch('addReaction', id)
			// TODO display immediately and add own cooldown
		}
	}
}
</script>
<style lang="stylus">
.c-reactions-bar
	position: relative
	width: 64px
	height: 56px
	.actions
		position: absolute
		bottom: 5px
		left: 0
		display: flex
		pointer-events: all
		background-color: $clr-white
		border: border-separator()
		border-radius: 24px
		padding: 4px
		transition: transform .3s ease
	.bunt-icon-button
		icon-button-style()
		&:not(:first-child)
			margin-left: 8px
	.emoji
		height: 28px
		width: @height
		display: inline-block
		background-image: url("~emoji-datasource-twitter/img/twitter/sheets-256/64.png")
		background-size: 5700% 5700%
	&:not(.expanded)
		.actions:hover
			cursor: pointer
			background-color: $clr-grey-100
		.bunt-icon-button
			pointer-events: none
	&.expanded
		.actions
			z-index: 801
			transform: translateX(calc(64px - 100% - 16px))
</style>

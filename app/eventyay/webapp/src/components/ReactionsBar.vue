<template lang="pug">
.c-reactions-bar(:class="{expanded}")
	.actions(@click="expand")
		bunt-icon-button(v-for="reaction of availableReactions", @click.stop="react(reaction.emoji)")
			.emoji(:style="reaction.style")
</template>
<script>
import { nativeToStyle as nativeEmojiToStyle } from 'lib/emoji'

export default {
	props: {
		expanded: Boolean
	},
	emits: ['expand'],
	data() {
		return {
			particlePool: [],
			freeParticles: [],
			overlayHeight: null
		}
	},
	computed: {
		availableReactions() {
			const emoji = ['👏', '❤️', '👍', '🤣', '😮']
			return emoji.map(e => ({emoji: e, style: nativeEmojiToStyle(e)}))
		}
	},
	methods: {
		expand() {
			if (this.expanded) return
			this.$emit('expand')
		},
		react(emoji) {
			this.$store.dispatch('addReaction', emoji)
			// TODO display immediately and add own cooldown
		}
	}
}
</script>
<style lang="stylus">
.c-reactions-bar
	position: relative
	margin-left: 10px
	height: 56px
	+above('m')
		right: 160px
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
		height: 27px !important
		width: 27px !important
		&:not(:first-child)
			margin-left: 8px
	.emoji
		height: 26px
		width: @height
		display: inline-block
	&:not(.expanded)
		width: 40px
		+below('m')
			left: -150px
		.actions:hover
			cursor: pointer
			background-color: $clr-grey-100
		.bunt-icon-button
			pointer-events: none
	&.expanded
		.actions
			transform: translateX(calc(50px - 21% - 15px));
			+above('m')
				transform: translateX(calc(50px - 21% - 50px));
</style>

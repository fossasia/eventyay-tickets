<template lang="pug">
.c-prompt(@click="allowCancel && $emit('close')")
	.prompt-wrapper(v-scrollbar.y="", @click.stop="")
		bunt-icon-button#btn-close(v-if="allowCancel", @click="$emit('close')") close
		slot.content
</template>
<script>
export default {
	props: {
		action: String, // block, ban, silence, unban, unsilence
		allowCancel: {
			type: Boolean,
			default: true
		}
	},
	data () {
		return {
		}
	},
	computed: {},
	created () {},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {}
}
</script>
<style lang="stylus">
.c-prompt
	position: fixed
	top: 0
	left: 0
	width: 100vw
	height: var(--vh100)
	z-index: 1000
	background-color: $clr-secondary-text-light
	display: flex
	justify-content: center
	align-items: center
	.prompt-wrapper
		card()
		display: flex
		flex-direction: column
		width: 480px
		max-height: 80vh
		#btn-close
			icon-button-style(style: clear)
			position: absolute
			top: 8px
			right: 8px
			z-index: 10
.prompt-enter-active, .prompt-leave-active
	transition: opacity .3s
.prompt-enter, .prompt-leave-to
	opacity: 0
</style>

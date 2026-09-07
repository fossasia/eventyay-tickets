<template lang="pug">
.c-prompt(@pointerdown="onPointerdown")
	.prompt-wrapper(ref="wrapper", @pointerdown.stop="")
		bunt-icon-button#btn-close(v-if="allowCancel", @click="$emit('close')") close
		slot.content
</template>
<script>
// FIXME when starting mousedown inside and finishing mouseup outside, prompt closes
import { Scrollbars } from 'buntpapier/src/directives/scrollbar'

export default {
	props: {
		action: String, // block, ban, silence, unban, unsilence
		allowCancel: {
			type: Boolean,
			default: true
		},
		scrollable: {
			type: Boolean,
			default: true
		}
	},
	emits: ['close'],
	mounted() {
		this.$nextTick(() => {
			if (!this.scrollable) return
			this.scrollbars = new Scrollbars(this.$refs.wrapper, {
				scrollY: true
			})
		})
	},
	methods: {
		onPointerdown(event) {
			if (!this.allowCancel) return
			event.stopPropagation()
			this.$el.addEventListener('pointerup', this.onPointerup)
		},
		onPointerup(event) {
			this.$el.removeEventListener('pointerup', this.onPointerup)
			if (event.target !== this.$el) return
			console.log(event)
			this.$emit('close')
		}
	}
}
</script>
<style lang="stylus">
.c-prompt
	position: fixed
	top: 0
	left: 0
	right: 0
	bottom: 0
	width: 100vw
	height: 100vh
	height: 100dvh
	height: var(--vh100, 100vh)
	z-index: 2000
	background-color: rgba(0, 0, 0, 0.54)
	display: flex
	justify-content: center
	align-items: safe center
	overflow-y: auto
	padding: 16px 0
	box-sizing: border-box
	.prompt-wrapper
		card()
		display: flex
		flex-direction: column
		width: 480px
		max-height: calc(100vh - 32px)
		max-height: calc(100dvh - 32px)
		max-height: calc(var(--vh100, 100vh) - 32px)
		min-height: 0
		flex-shrink: 1
		position: relative
		+below('m')
			width: 100vw
			max-height: calc(100vh - 32px)
			max-height: calc(100dvh - 32px)
			max-height: calc(var(--vh100, 100vh) - 32px)
		> .content
			display: flex
			flex-direction: column
			flex: 1 1 auto
			min-height: 0
			overflow: hidden
		#btn-close
			icon-button-style(style: clear)
			position: absolute
			top: 8px
			right: 8px
			z-index: 10
.prompt-enter-active, .prompt-leave-active
	transition: opacity .3s
.prompt-enter-from, .prompt-leave-to
	opacity: 0
</style>

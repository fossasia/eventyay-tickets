<template lang="pug">
.c-emoji-picker-button
	bunt-icon-button.btn-emoji-picker(ref="button", @click="toggle")
		svg(v-if="iconStyle === 'plain'", xmlns="http://www.w3.org/2000/svg", viewBox="0 0 24 24")
			path(d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0m0 22C6.486 22 2 17.514 2 12S6.486 2 12 2s10 4.486 10 10-4.486 10-10 10")
			path(d="M8 7a2 2 0 1 0-.001 3.999A2 2 0 0 0 8 7M16 7a2 2 0 1 0-.001 3.999A2 2 0 0 0 16 7M15.232 15c-.693 1.195-1.87 2-3.349 2-1.477 0-2.655-.805-3.347-2H15m3-2H6a6 6 0 1 0 12 0")
		svg(v-if="iconStyle === 'plus'", xmlns="http://www.w3.org/2000/svg", viewBox="0 0 28.695 28.62")
			path(d="m8 11.62a2 2 0 1 0-1e-3 3.999 2 2 0 0 0 1e-3 -3.999m8 0a2 2 0 1 0-1e-3 3.999 2 2 0 0 0 1e-3 -3.999m-0.768 8c-0.693 1.195-1.87 2-3.349 2-1.477 0-2.655-0.805-3.347-2h6.464m3-2h-12a6 6 0 1 0 12 0")
			path(d="m23.047 0a1 1 0 0 0-1 1v3.6484h-3.6484a1 1 0 0 0-1 1 1 1 0 0 0 1 1h3.6484v3.6484a1 1 0 0 0 1 1 1 1 0 0 0 1-1v-3.6484h3.6484a1 1 0 0 0 1-1 1 1 0 0 0-1-1h-3.6484v-3.6484a1 1 0 0 0-1-1z")
			path(d="m13.242 4.6836c-5.0865-0.52948-9.9583 2.2302-12.119 6.8652-2.1608 4.635-1.1425 10.142 2.5332 13.697 3.6757 3.5555 9.2129 4.3899 13.773 2.0762 4.5606-2.3138 7.1553-7.2758 6.457-12.342a1 1 0 0 0-1.127-0.85352 1 1 0 0 0-0.85352 1.127c0.58284 4.2284-1.5744 8.352-5.3809 10.283-3.8065 1.9312-8.4106 1.2391-11.479-1.7285-3.068-2.9676-3.9129-7.5455-2.1094-11.414 1.8036-3.8686 5.8522-6.1626 10.098-5.7207a1 1 0 0 0 1.0977-0.89062 1 1 0 0 0-0.89062-1.0996z")
	.emoji-picker-blocker(v-if="showEmojiPicker", @click="showEmojiPicker = false")
	emoji-picker(v-if="showEmojiPicker", ref="picker", @selected="selected")
</template>
<script>
import { createPopper } from '@popperjs/core'
import EmojiPicker from 'components/EmojiPicker'

export default {
	components: { EmojiPicker },
	props: {
		iconStyle: {
			type: String,
			default: 'plain'
		},
		placement: {
			type: String,
			default: 'top-start'
		},
		strategy: {
			type: String,
			default: 'absolute'
		},
		offset: {
			type: Array,
			default: () => ([-3, 8])
		}
	},
	data () {
		return {
			showEmojiPicker: false
		}
	},
	computed: {},
	created () {},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {
		async toggle (event) {
			if (this.showEmojiPicker) {
				this.showEmojiPicker = false
				return
			}
			this.showEmojiPicker = true
			await this.$nextTick()
			createPopper(this.$refs.button.$el, this.$refs.picker.$el, {
				placement: this.placement,
				strategy: this.strategy,
				modifiers: [
					{
						name: 'offset',
						options: {
							offset: this.offset,
						},
					},
				]
			})
		},
		selected (emoji) {
			this.showEmojiPicker = false
			this.$emit('selected', emoji)
		}
	}
}
</script>
<style lang="stylus">
.c-emoji-picker-button
	.btn-emoji-picker
		icon-button-style()
		// height: 36px
		// width: @height
		// box-sizing: border-box
		// padding: 8px
		// &:hover
		// 	border-radius: 50%
		// 	background-color: $clr-grey-100
		svg
			path
				fill: $clr-primary-text-light
	.emoji-picker-blocker
		position: fixed
		top: 0
		left: 0
		width: 100vw
		height: var(--vh100)
		z-index: 800
	.c-emoji-picker
		z-index: 801
</style>

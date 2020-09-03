<template lang="pug">
.c-menu-dropdown
	.ui-background-blocker(v-if="blockBackground && value", @click="$emit('input', false)")
	slot(name="button", :toggle="toggle")
	.menu(v-if="value", ref="menu")
		slot(name="menu")
</template>
<script>
import { createPopper } from '@popperjs/core'

export default {
	props: {
		value: Boolean,
		placement: {
			type: String,
			default: 'bottom'
		},
		blockBackground: {
			type: Boolean,
			default: true
		}
	},
	methods: {
		async toggle (event) {
			if (this.value) {
				this.$emit('input', false)
				return
			}
			this.$emit('input', true)
			await this.$nextTick()
			const button = event.target.closest('.bunt-icon-button, .bunt-button') || event.target
			createPopper(button, this.$refs.menu, {
				placement: this.placement
			})
		},
		close () {
			this.isOpen = false
		}
	}
}
</script>
<style lang="stylus">
.c-menu-dropdown
	.menu
		card()
		z-index: 850
		display: flex
		flex-direction: column
		min-width: 240px
		padding: 4px 0
		> *
			flex: none
			height: 32px
			font-size: 16px
			line-height: 32px
			padding: 0 0 0 16px
			user-select: none
			&:not(.divider)
				cursor: pointer
				&:hover
					background-color: var(--clr-input-primary-bg)
					color: var(--clr-input-primary-fg)
			&.divider
				font-size: 12px
				font-weight: 600
				border-bottom: border-separator()
</style>

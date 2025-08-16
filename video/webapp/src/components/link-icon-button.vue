<template lang="pug">
router-link.bunt-icon-button(:to="to", :class="{disabled}", v-tooltip="tooltipOptions || {text: tooltip, placement: tooltipPlacement, fixed: tooltipFixed}", :aria-disabled="disabled", :aria-label="tooltip || iconClass()")
	i.bunt-icon.mdi(v-if="iconClass()", :class="[iconClass()]", aria-hidden="true")
	template(v-else)
		slot
	ripple-ink(v-if!="!noInk && !disabled")
</template>
<script>
import RippleInk from 'buntpapier/src/mixins/ripple-ink'
import iconHelper from 'buntpapier/src/helpers/icon'

export default {
	name: 'LinkIconButton',
	mixins: [
		RippleInk
	],
	props: {
		to: Object,
		disabled: {
			type: Boolean,
			default: false
		},
		noInk: {
			type: Boolean,
			default: false
		},
		tooltip: String,
		tooltipPlacement: {
			type: String,
			default: 'bottom'
		},
		tooltipFixed: {
			type: Boolean,
			default: false
		},
		tooltipOptions: Object
	},
	data() {
		return {
			showTooltip: false
		}
	},
	methods: {
		iconClass() {
			const slot = this.$slots.default ? this.$slots.default() : []
			if (slot.length && slot[0].type) return
			return slot.length ? iconHelper.getClass(slot[0].children) : null
		}
	}
}
</script>

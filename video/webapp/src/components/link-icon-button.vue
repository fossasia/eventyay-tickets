<template lang="pug">
router-link.bunt-icon-button(:to="to", :class="{disabled}", v-tooltip="tooltipOptions || {text: tooltip, placement: tooltipPlacement, fixed: tooltipFixed}", :aria-disabled="disabled", :aria-label="tooltip || iconClass()")
	i.bunt-icon.mdi(v-if="iconClass()", :class="[iconClass()]", aria-hidden="true")
	slot(v-else)
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
	data () {
		return {
			showTooltip: false
		}
	},
	methods: {
		iconClass () {
			if (this.$slots.default[0].tag) return
			return iconHelper.getClass(this.$slots.default[0].text)
		}
	}
}
</script>

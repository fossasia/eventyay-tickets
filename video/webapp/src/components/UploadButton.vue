<template lang="pug">
.c-upload-button
	label(for="file-chooser")(:class="_buttonClass", v-tooltip="tooltipOptions || {text: _tooltip, placement: tooltipPlacement, fixed: tooltipFixed}")
		i.bunt-icon.mdi(v-if="iconClass()", :class="iconClass()")
		.bunt-button-content
			.bunt-button-text
				slot
		ripple-ink
	input#file-chooser(type="file", @change="$emit('change', $event)", :accept="accept" :multiple="multiple")
</template>
<script>
import RippleInk from 'buntpapier/src/mixins/ripple-ink'
import iconHelper from 'buntpapier/src/helpers/icon'

export default {
	mixins: [
		RippleInk
	],
	props: {
		accept: String,
		multiple: Boolean,
		tooltip: String,
		icon: String,
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
		}
	},
	computed: {
		_tooltip () {
			return this.errorMessage ? this.errorMessage : this.tooltip
		},
		_buttonClass () {
			return this.icon ? 'bunt-icon-button' : 'bunt-button'
		}
	},
	methods: {
		iconClass () {
			if (!this.icon) return
			return iconHelper.getClass(this.icon)
		}
	}
}
</script>
<style lang="stylus">
.c-upload-button
	#file-chooser
		display: none
	.bunt-icon-button
		pointer-events: auto
		position: relative
		top: 0
		left: 0
		transform: none
		height: 100%
		width: 100%
</style>

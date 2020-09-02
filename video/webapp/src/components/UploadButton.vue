<template lang="pug">
.c-upload-button
	label(for="file-chooser").bunt-button(v-tooltip="tooltipOptions || {text: _tooltip, placement: tooltipPlacement, fixed: tooltipFixed}")
		.bunt-button-content
			.bunt-button-text
				slot
		ripple-ink
	input#file-chooser(type="file", @change="$emit('change', $event)", :accept="accept")
</template>
<script>
import RippleInk from 'buntpapier/src/mixins/ripple-ink'

export default {
	mixins: [
		RippleInk
	],
	props: {
		accept: String,
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
		}
	},
	computed: {
		_tooltip () {
			return this.errorMessage ? this.errorMessage : this.tooltip
		}
	},
	methods: {}
}
</script>
<style lang="stylus">
.c-upload-button
	#file-chooser
		display: none
</style>

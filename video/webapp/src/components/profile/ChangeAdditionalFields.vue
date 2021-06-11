<template lang="pug">
.c-additional-fields
	template(v-for="field of fields")
		bunt-input(v-if="field.type === 'text'", :name="field.label", :label="field.label", v-model="value[field.id]", :disabled="disabled")
		bunt-input-outline-container(v-if="field.type === 'textarea'", :label="field.label", :name="field.label", :class="{disabled: disabled}")
			textarea(slot-scope="{focus, blur}", @focus="focus", @blur="blur", v-model="value[field.id]", :disabled="disabled")
		bunt-select(v-if="field.type === 'select'", v-model="value[field.id]", :label="field.label", name="field.label", :options="field.choices.split(', ')", :disabled="disabled")
</template>
<script>
import { mapState } from 'vuex'

export default {
	props: {
		value: Object,
		disabled: {
			type: Boolean,
			default: false
		}
	},
	computed: {
		...mapState(['world']),
		fields () {
			return this.world?.profile_fields
		}
	}
}
</script>
<style lang="stylus">
.c-additional-fields
	display: flex
	flex-direction: column
	> *
		width: 320px
		max-width: 100%
	.bunt-input-outline-container
		margin-bottom 16px
		textarea
			font-family $font-stack
			font-size 16px
			background-color transparent
			border none
			outline none
			resize vertical
			min-height 250px
			padding 0 8px
	.bunt-input-outline-container.disabled
		background-color $clr-grey-200
</style>

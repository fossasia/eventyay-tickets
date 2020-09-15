<template lang="pug">
.c-additional-fields
	template(v-for="field of fields")
		bunt-input(v-if="field.type === 'text'", :name="field.label", :label="field.label", v-model="value[field.id]")
		bunt-input-outline-container(v-if="field.type === 'textarea'", :label="field.label", :name="field.label")
			textarea(slot-scope="{focus, blur}", @focus="focus", @blur="blur", v-model="value[field.id]")
		bunt-select(v-if="field.type === 'select'", v-model="value[field.id]", :label="field.label", name="field.label", :options="field.choices.split(', ')")
</template>
<script>
import { mapState } from 'vuex'

export default {
	props: {
		value: Object,
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
</style>

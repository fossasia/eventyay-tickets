<template lang="pug">
.c-additional-fields
	bunt-input(v-for="field of FIELDS", :name="field", :label="field", v-model="value[field]")
</template>
<script>

const FIELDS = [
	'Some field',
	'Another field',
]

export default {
	props: {
		value: Object
	},
	data () {
		return {
			FIELDS
		}
	}
}
</script>
<style lang="stylus">
</style>

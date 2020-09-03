<template lang="pug">
.c-additional-fields
	span(v-for="field of fields")
		bunt-input(v-if="field.type === 'text'", :name="field.label", :label="field.label", v-model="value[field.label]")
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
			return this.world?.user_profile?.additional_fields
		}
	}
}
</script>
<style lang="stylus">
</style>

<template lang="pug">
.c-exhibitor
</template>
<script>
import api from 'lib/api'

export default {
	props: {
		exhibitorId: String
	},
	data () {
		return {
			exhibitor: null
		}
	},
	computed: {},
	async created () {
		this.exhibitor = await api.call('exhibition.get', {exhibitor: this.exhibitorId})
	},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {}
}
</script>
<style lang="stylus">
</style>

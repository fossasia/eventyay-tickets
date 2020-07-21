<template lang="pug">
.c-exhibition
	.exhibitors(v-if="exhibitors", v-scrollbar.y="")
		router-link.exhibitor(v-for="exhibitor of exhibitors", :to="{name: 'exhibitor', params: {exhibitorId: exhibitor.id}}")
			.name {{ exhibitor.name }}
			img.logo(:src="exhibitor.logo")
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import api from 'lib/api'

export default {
	props: {
		room: Object
	},
	components: {},
	data () {
		return {
			exhibitors: null
		}
	},
	computed: {},
	async created () {
		this.exhibitors = (await api.call('exhibition.list', {room: this.room.id})).exhibitors
	},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {}
}
</script>
<style lang="stylus">
.c-exhibition
	display: grid
</style>

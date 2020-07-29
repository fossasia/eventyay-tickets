<template lang="pug">
.c-exhibition
	.exhibitors(v-if="exhibitors", v-scrollbar.y="")
		.exhibitor-grid
			router-link.exhibitor(v-for="exhibitor of exhibitors", :to="{name: 'exhibitor', params: {exhibitorId: exhibitor.id}}", :class="'exhibitor-' + exhibitor.size")
				.content
					.header
						img.logo(:src="exhibitor.logo" height="150" width="150")
						.name(v-if="exhibitor.size != '1x1'") {{ exhibitor.name }}
						.tagline(v-if="exhibitor.size != '1x1'") {{ exhibitor.tagline }}
					.text(v-if="exhibitor.size == '3x3'") {{ exhibitor.short_text }}
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
	width: 100%
	height: 100%
	.exhibitors
		height: 100%
	.exhibitor-grid
		display: grid
		grid-template-columns: repeat(auto-fill, 180px)
		grid-auto-rows: 180px
		grid-auto-flow: dense // denser grid, but breaks order
		gap: 15px
		padding: 15px
		max-height: inherit;
	.exhibitor
		.content
			height: 100%
			color: $clr-primary-text-light
			card()
			.header
				min-height: 150px
				padding: 15px
			.logo
				float: left
			.tagline
				font-size: 1.2rem
				text-rendering: optimizelegibility
				font-weight: bold
				padding: 0.83rem
				margin-left: 150px
			.name
				font-size: 1.8rem
				text-rendering: optimizelegibility
				font-weight: bold
				padding: 0.83rem
				margin-left: 150px
			.text
				font-size: 1.2rem
				padding: 15px
	.exhibitor .content:hover
		card-raised()
	.exhibitor-1x1
		grid-area: span 1 / span 1
	.exhibitor-1x3
		grid-area: span 1 / span 3
	.exhibitor-3x3
		grid-area: span 3 / span 3

	+below('m')
		.exhibitor-1x3
			grid-area: span 1 / span 2
		.exhibitor-3x3
			grid-area: span 3 / span 2
</style>

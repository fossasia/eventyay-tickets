<template lang="pug">
.c-exhibition
	scrollbars.exhibitors(v-if="exhibitors", y)
		router-link.exhibitor(v-for="exhibitor of exhibitors", :to="{name: 'exhibitor', params: {exhibitorId: exhibitor.id}}", :class="'exhibitor-' + exhibitor.size")
			img.logo(:src="exhibitor.logo", :alt="exhibitor.name")
			.short-text {{ exhibitor.short_text }}
			.actions
				bunt-button more
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
$grid-size = 280px
$logo-height = 130px
$logo-height-medium = 160px
$logo-height-large = 427px

.c-exhibition
	flex: auto
	display: flex
	flex-direction: column
	min-height: 0
	background-color: $clr-grey-50
	.exhibitors .scroll-content
		flex: auto
		display: grid
		grid-template-columns: repeat(auto-fill, $grid-size)
		grid-auto-rows: $grid-size
		grid-auto-flow: dense // denser grid, but breaks order
		gap: 16px
		padding: 16px
		justify-content: center
	.exhibitor
		background-color: $clr-white
		border: border-separator()
		border-radius: 4px
		display: flex
		flex-direction: column
		padding: 8px
		cursor: pointer
		img.logo
			object-fit: contain
			max-width: 100%
			height: $logo-height
			min-height: $logo-height
			margin: 0 1px
		.short-text
			margin-top: 12px
			color: $clr-primary-text-light
			display: -webkit-box
			-webkit-line-clamp: 5
			-webkit-box-orient: vertical
			overflow: hidden
		.actions
			flex: auto
			display: flex
			justify-content: flex-end
			align-items: flex-end
			.bunt-button
				themed-button-secondary()
		&:hover
			border: 1px solid var(--clr-primary)
	.exhibitor-1x1
		grid-area: span 1 / span 1
	.exhibitor-3x1
		grid-area: span 1 / span 2
		img.logo
			height: $logo-height-medium
			min-height: $logo-height-medium
			margin: 0
	.exhibitor-3x3
		grid-area: span 2 / span 3
		img.logo
			height: $logo-height-large
			min-height: $logo-height-large
			margin: 0

	// below 3 wide grid
	+below(904px)
		.exhibitor-3x3
			grid-area: span 2 / span 2
	// disolve grid below 2 wide
	+below(607px)
		.exhibitors .scroll-content
			display: flex
			justify-content: flex-start
		.exhibitor
			flex: none
			img.logo
				height: auto
				min-height: 0
		.exhibitor-1x1
			img.logo
				max-height: $logo-height-medium
</style>

<template lang="pug">
.c-exhibitors
	.header
		h2 {{ $t("Exhibitors:headline:text") }}
	.exhibitor-list
		.header
			.exhibitor-label {{ $t("Exhibitors:exhibitor:label") }}
			.actions
					bunt-button.btn-create(v-if="hasPermission('world:rooms.create.exhibition')", @click="$router.push({name: 'exhibitors:exhibitor', params: {exhibitorId: ''}})") {{ $t('Exhibitors:create:label') }}
		RecycleScroller.tbody.bunt-scrollbar(v-if="exhibitors", :items="exhibitors", :item-size="48", v-slot="{item: exhibitor}", v-scrollbar.y="")
			router-link.exhibitor(:to="{name: 'exhibitors:exhibitor', params: {exhibitorId: exhibitor.id}}").table-row
				.name {{ exhibitor.name }}
		bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import api from 'lib/api'
import {mapGetters} from 'vuex'

export default {
	components: {},
	data () {
		return {
			exhibitors: []
		}
	},
	computed: {
		...mapGetters(['hasPermission']),
	},
	async created () {
		this.exhibitors = (await api.call('exhibition.list.all', {})).exhibitors // TODO: get exhibitions based on permission
	},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {}
}
</script>
<style lang="stylus">
@import '~styles/flex-table'

.c-exhibitors
	display flex
	flex-direction column
	background-color $clr-white
	min-height 0
	.header
		height 56px
		border-bottom border-separator()
		padding 0 16px
		display flex
		align-items center
		> *
			margin 0
	.exhibitor-list
		flex-table()
		.header
			justify-content space-between
			.actions
				display flex
				flex none
				.bunt-button:not(:last-child)
					margin-right 16px
				.btn-create
					themed-button-primary()
		.exhibitor-label
			padding-left 0
		.name
			flex auto
			ellipsis()
			color $clr-primary-text-light
		.exhibitor:not(:hover)
			.actions .bunt-button
				display none
		.exhibitor:hover
			.actions .placeholder
				display none
</style>

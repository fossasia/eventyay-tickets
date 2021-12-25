<template lang="pug">
.c-posters
	.ui-page-header
		h2 {{ $t("poster-manager/index:headline:text") }}
	.poster-list
		.header
			.title {{ $t("poster-manager/index:poster:label") }}
			.actions
					bunt-link-button.btn-create(v-if="hasPermission('world:rooms.create.poster')", :to="{name: 'posters:create-poster'}") {{ $t('poster-manager/index:create:label') }}
		RecycleScroller.tbody.bunt-scrollbar(v-if="posters", :items="posters", :item-size="48", v-slot="{item: poster}", v-scrollbar.y="")
			router-link.poster(:to="{name: 'posters:poster', params: {posterId: poster.id}}").table-row
				.title {{ poster.title }}
		bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
// TODO
// -more list columns (category)
import { mapGetters } from 'vuex'
import api from 'lib/api'

export default {
	data () {
		return {
			posters: null
		}
	},
	computed: {
		...mapGetters(['hasPermission']),
	},
	async created () {
		this.posters = (await api.call('poster.list.all', {}))
	}
}
</script>
<style lang="stylus">
@import '~styles/flex-table'

.c-posters
	display: flex
	flex-direction: column
	background-color: $clr-white
	min-height: 0
	.poster-list
		flex-table()
		.header
			justify-content: space-between
			align-items: center
			.actions
				display: flex
				flex: none
				.btn-create
					themed-button-primary()
		.title
			flex: auto
			ellipsis()
			color: $clr-primary-text-light
</style>

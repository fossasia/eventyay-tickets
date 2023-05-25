<template lang="pug">
.c-admin-kiosk
	.header
		.actions
			h2 Kiosks
			bunt-link-button.btn-create(:to="{name: 'admin:kiosks:new'}") Create a new kiosk
		bunt-input.search(name="search", placeholder="Search kiosks", icon="search", v-model="search")
	.kiosks-list
		.header
			.name Name
			.room Room
		.tbody(v-if="filteredKiosks", v-scrollbar.y="")
			router-link.kiosk.table-row(v-for="kiosk of filteredKiosks", :to="{name: 'admin:kiosks:item', params: {kioskId: kiosk.id}}")
				.name {{ kiosk.profile.display_name }}
				.room {{ roomsLookup[kiosk.profile.room_id] ? roomsLookup[kiosk.profile.room_id].name : '' }}
		bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import { mapGetters } from 'vuex'
import api from 'lib/api'
import fuzzysearch from 'lib/fuzzysearch'

export default {
	name: 'AdminKiosks',
	data () {
		return {
			kiosks: null,
			search: ''
		}
	},
	computed: {
		...mapGetters(['roomsLookup']),
		filteredKiosks () {
			if (!this.kiosks) return
			if (!this.search) return this.kiosks
			return this.kiosks.filter(kiosk => kiosk.id === this.search.trim() || fuzzysearch(this.search.toLowerCase(), kiosk.profile.display_name.toLowerCase()))
		}
	},
	async created () {
		this.kiosks = (await api.call('user.list', {type: 'kiosk'})).results
	}
}
</script>
<style lang="stylus">
@import '~styles/flex-table'

.c-admin-kiosk
	display: flex
	flex-direction: column
	min-height: 0
	background-color: $clr-white
	.header
		justify-content: space-between
		background-color: $clr-grey-50
		.actions
			display: flex
			flex: none
			align-items: center
			.bunt-button:not(:last-child)
				margin-right: 16px
			.btn-create
				themed-button-primary()
	h2
		margin: 16px
	.search
		input-style(size: compact)
		padding: 0
		margin: 8px
		flex: none
		background-color: $clr-white
	.kiosks-list
		flex-table()
		.kiosk
			display: flex
			align-items: center
			color: $clr-primary-text-light
		.name, .room
			flex: 1
			ellipsis()
</style>

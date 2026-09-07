<template lang="pug">
.c-admin-kiosk
	.ui-page-header
		bunt-icon-button(@click="$router.push({name: 'organizer'})", :tooltip="$t('Back to Overview')", tooltip-placement="bottom-start", :tooltip-fixed="true") arrow-left
		h2 {{ $t('Kiosks') }}
		.actions
			bunt-link-button.btn-create(:to="{name: 'admin:kiosks:new'}") {{ $t('Create a new kiosk') }}
			bunt-input.search(name="search", :placeholder="$t('Search kiosks')", icon="search", v-model="search")
	.kiosks-list
		.header
			.name {{ $t('Name') }}
			.room {{ $t('Room') }}
			.actions-col {{ $t('Launch') }}
		.tbody(v-if="filteredKiosks", v-scrollbar.y="")
			.kiosk.table-row(v-for="kiosk of filteredKiosks", :key="kiosk.id")
				router-link.kiosk-info(:to="{name: 'admin:kiosks:item', params: {kioskId: kiosk.id}}")
					.name {{ kiosk.profile.display_name }}
					.room {{ roomsLookup[kiosk.profile.room_id] ? roomsLookup[kiosk.profile.room_id].name : '' }}
				.actions-col
					a.open-link(:href="getKioskLoginUrl(kiosk)", target="_blank", rel="noopener", :title="$t('Open kiosk in new tab')", @click.stop)
						i.mdi.mdi-open-in-new
		bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import { mapGetters } from 'vuex'
import api from 'lib/api'
import fuzzysearch from 'lib/fuzzysearch'

export default {
	name: 'AdminKiosks',
	data() {
		return {
			kiosks: null,
			search: ''
		}
	},
	computed: {
		...mapGetters(['roomsLookup']),
		filteredKiosks() {
			if (!this.kiosks) return
			if (!this.search) return this.kiosks
			return this.kiosks.filter(kiosk => kiosk.id === this.search.trim() || fuzzysearch(this.search.toLowerCase(), kiosk.profile.display_name.toLowerCase()))
		}
	},
	async created() {
		this.kiosks = (await api.call('user.list', {type: 'kiosk'})).results
	},
	methods: {
		getKioskLoginUrl(kiosk) {
			return `${window.location.origin}/login/${kiosk.token}`
		}
	}
}
</script>
<style lang="stylus">
@import 'flex-table'

.c-admin-kiosk
	display: flex
	flex-direction: column
	min-height: 0
	background-color: $clr-white
	.ui-page-header
		.actions
			display: flex
			align-items: center
			gap: 8px
			margin-left: auto
			.btn-create
				themed-button-primary()
		.search
			input-style(size: compact)
			padding: 0
			margin: 0
			flex: none
			background-color: $clr-white
	.kiosks-list
		flex-table()
		.kiosk
			display: flex
			align-items: center
			color: $clr-primary-text-light
			padding-right: 8px
		.kiosk-info
			display: flex
			flex: 1
			align-items: center
			color: inherit
			text-decoration: none
			min-width: 0
		.name, .room
			flex: 1
			ellipsis()
		.actions-col
			flex: 0 0 60px
			display: flex
			align-items: center
			justify-content: flex-end
			.open-link
				display: flex
				align-items: center
				justify-content: center
				width: 32px
				height: 32px
				border-radius: 4px
				color: $clr-primary
				text-decoration: none
				transition: background-color 0.15s ease
				&:hover
					background-color: $clr-grey-200
				.mdi
					font-size: 18px
</style>

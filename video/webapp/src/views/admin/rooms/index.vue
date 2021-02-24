<template lang="pug">
.c-admin-rooms
	.header
		.actions
			h2 Rooms
			bunt-link-button.btn-create(:to="{name: 'admin:rooms:new'}") Create a new room
		bunt-input.search(name="search", placeholder="Search rooms", icon="search", v-model="search")
	.rooms-list
		.header
			.id ID
			.prio Priority
			.name Name
		RecycleScroller.tbody.bunt-scrollbar(v-if="filteredRooms", :items="filteredRooms", :item-size="48", v-slot="{item: room}", v-scrollbar.y="")
			router-link.room.table-row(:to="{name: 'admin:rooms:item', params: {roomId: room.id}}", :class="{error: room.error, updating: room.updating}")
				.id(:title="room.id") {{ room.id }}
				.prio {{ room.sorting_priority }}
				.name {{ room.name }}
		bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import api from 'lib/api'
import fuzzysearch from 'lib/fuzzysearch'

export default {
	name: 'AdminRooms',
	data () {
		return {
			rooms: null,
			search: ''
		}
	},
	computed: {
		filteredRooms () {
			if (!this.rooms) return
			if (!this.search) return this.rooms
			return this.rooms.filter(room => room.id === this.search.trim() || fuzzysearch(this.search.toLowerCase(), room.name.toLowerCase()))
		}
	},
	async created () {
		this.rooms = await api.call('room.config.list')
	}
}
</script>
<style lang="stylus">
@import '~styles/flex-table'

.c-admin-rooms
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
	.rooms-list
		flex-table()
		.room
			display: flex
			align-items: center
			color: $clr-primary-text-light
		.id
			width: 128px
			flex: none
			ellipsis()
		.prio
			width: 64px
			flex: none
			text-align: right
			ellipsis()
		.name
			flex: auto
			ellipsis()
</style>

<template lang="pug">
.c-admin-rooms
	.header
		.actions
			h2 Rooms
			bunt-link-button.btn-create(:to="{name: 'admin:rooms:new'}") Create a new room
		bunt-input.search(name="search", placeholder="Search rooms", icon="search", v-model="search")
	.rooms-list
		.header
			.drag
			.name Name
		SlickList.tbody(v-if="filteredRooms", v-model="rooms", lockAxis="y", :useDragHandle="true", v-scrollbar.y="", @input="onListSort")
			RoomListItem(v-for="(room, index) of rooms" :index="index", :key="index", :room="room")
		bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
// TODO show inferred type
import api from 'lib/api'
import fuzzysearch from 'lib/fuzzysearch'
import { SlickList } from 'vue-slicksort'
import RoomListItem from './RoomListItem'

export default {
	name: 'AdminRooms',
	components: { SlickList, RoomListItem },
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
	},
	methods: {
		async onListSort () {
			this.rooms = await api.call('room.config.reorder', this.rooms.map(room => room.id))
			// TODO error handling
		}
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
		.drag
			width: 24px
		.name
			flex: auto
			ellipsis()
</style>

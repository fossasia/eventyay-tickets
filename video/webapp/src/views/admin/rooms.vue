<template lang="pug">
.c-admin-rooms
	.header
		h2 Rooms
		.search
			bunt-input.search(name="search", placeholder="Search rooms", icon="search", v-model="search")
	.rooms-list
		.header
			.avatar
			.id ID
			.name Name
			.actions
				bunt-button.btn-save(@click="showCreateRoomPrompt = true") Create new
		RecycleScroller.tbody.bunt-scrollbar(v-if="filteredRooms", :items="filteredRooms", :item-size="48", v-slot="{item: room}", v-scrollbar.y="")
			router-link(:to="{name: 'admin:room', params: {editRoomId: room.id}}").room.table-row(:class="{error: room.error, updating: room.updating}")
				.id(:title="room.id") {{ room.id }}
				.name {{ room.name }}
		bunt-progress-circular(v-else, size="huge", :page="true")
	transition(name="prompt")
		create-room-prompt(v-if="showCreateRoomPrompt", @close="showCreateRoomPrompt = false")
</template>
<script>
// TODO
// - search
import api from 'lib/api'
import fuzzysearch from 'lib/fuzzysearch'
import CreateRoomPrompt from 'components/config/CreateRoomPrompt'

export default {
	name: 'AdminRooms',
	components: {CreateRoomPrompt},
	data () {
		return {
			rooms: null,
			search: '',
			showCreateRoomPrompt: false,
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
		justify-content space-between
		background-color: $clr-grey-50
		.actions
			display flex
			flex none
			.bunt-button:not(:last-child)
				margin-right 16px
			.btn-save
				themed-button-primary()
	h2
		margin: 16px
	.search
		input-style(size: compact)
		padding: 0
		margin: 8px
		flex: none
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
		.name
			flex: auto
			ellipsis()
		.actions
			flex: none
			width: 200px
			flex: none
			padding: 0 24px 0 0
			display: flex
			align-items: center
			justify-content: flex-end
			.placeholder
				flex: none
				color: $clr-secondary-text-light
			.btn-edit
				button-style(style: clear, color: $clr-primary, text-color: $clr-primary)
			.btn-delete
				button-style(style: clear, color: $clr-danger, text-color: $clr-danger)
		.room:not(:hover):not(.error):not(.updating)
			.actions .bunt-button, .actions .bunt-link-button
				display: none
		.room:hover, .room.error, .room.updating
			.actions .placeholder
				display: none
</style>

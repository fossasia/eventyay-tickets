<template lang="pug">
.c-admin-rooms
	.header
		h2 Rooms
		bunt-input.search(name="search", placeholder="Search rooms", icon="search", v-model="search")
	.rooms-list
		.header
			.avatar
			.id ID
			.name Name
			.actions
		RecycleScroller.tbody.bunt-scrollbar(v-if="filteredRooms", :items="filteredRooms", :item-size="48", v-slot="{item: room}", v-scrollbar.y="")
			.room.table-row(:class="{error: room.error, updating: room.updating}")
				.id(:title="room.id") {{ room.id }}
				.name {{ room.name }}
				.actions
					.placeholder.mdi.mdi-dots-horizontal
					bunt-button.btn-delete(
						:loading="room.updating === 'delete'",
						:error-message="(room.error && room.error.action === 'delete') ? room.error.message : null",
						tooltipPlacement="left",
						@click="doAction(room, 'delete')", :key="`${room.id}-delete`")
						| delete
					bunt-link-button.btn-edit(
						tooltipPlacement="left",
						:to="{name: 'admin:room', params: {editRoomId: room.id}}"
						)
						| edit
		bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
// TODO
// - search
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
		this.load()
	},
	methods: {
		async load () {
			this.rooms = []
			this.rooms = (await api.call('room.config.list')).map(room => {
				return {
					...room,
					updating: null,
					error: null
				}
			})
		},
		async doAction (room, action, postState) {
			room.updating = action
			room.error = null
			try {
				await api.call(`room.${action}`, {room: room.id})
				if (action === 'delete') {
					this.load()
				}
			} catch (error) {
				room.error = {
					action,
					message: this.$t(`error:${error.code}`)
				}
			}
			room.updating = null
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
		background-color: $clr-grey-50
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

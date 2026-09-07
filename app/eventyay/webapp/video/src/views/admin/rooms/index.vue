<template lang="pug">
.c-admin-rooms
	.ui-page-header
		bunt-icon-button(@click="$router.push({name: 'organizer'})", :tooltip="$t('Back to Overview')", tooltip-placement="bottom-start", :tooltip-fixed="true") arrow-left
		h2 {{ $t('Rooms & Stages') }}
		.actions
			VideoProviderDropdown(
				:label="$t('Create Room')",
				:show-empty-message="true",
				@select="createRoomWithProvider"
			)
			.export-actions(v-if="canExportBroadcastConfiguration")
				a.export-button(:href="exportUrl('xlsx')") {{ $t('Export XLSX') }}
				a.export-button.secondary(:href="exportUrl('csv-excel')") {{ $t('CSV') }}
			bunt-input.search(name="search", :placeholder="$t('Search rooms')", icon="search", v-model="search")
	.error(v-if="error")
		span {{ $t('Failed to load rooms.') }}
		span(v-if="errorCode")  ({{ errorCode }})
		span(v-if="errorCode === 'protocol.denied'")  {{ $t('You likely lack admin permissions.') }}
	.rooms-list(v-else)
		.header
			.drag
			.name {{ $t('Name') }}
		SlickList.tbody(v-if="rooms", v-model:list="rooms", lockAxis="y", :useDragHandle="true", helperClass="sorting-helper", v-scrollbar.y="", @update:list="onListSort")
			RoomListItem(
				v-for="(room, index) of rooms",
				:index="index",
				:key="room.id",
				:room="room",
				:to="getRoomTargetRoute(room)",
				:disabled="!!search",
				v-show="isRoomVisible(room)"
			)
		bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import api from 'lib/api'
import fuzzysearch from 'lib/fuzzysearch'
import { inferType, isChatManagedRoom, mergeReorderedIds } from 'lib/room-types'
import { mapGetters } from 'vuex'
import { SlickList } from 'vue-slicksort'
import VideoProviderDropdown from 'components/VideoProviderDropdown'
import RoomListItem from './RoomListItem'

export default {
	name: 'AdminRooms',
	components: { SlickList, RoomListItem, VideoProviderDropdown },
	data() {
		return {
			allRooms: null,
			rooms: null,
			search: '',
			error: null,
			errorCode: null,
			_unwatchConnected: null
		}
	},
	watch: {
		'$store.state.rooms'(storeRooms) {
			if (!Array.isArray(this.allRooms) || !Array.isArray(storeRooms)) return
			const currentIds = this.allRooms.map(r => r.id)
			const storeIds = storeRooms.map(r => r.id)
			const changed =
				currentIds.length !== storeIds.length ||
				currentIds.some((id, i) => id !== storeIds[i])
			if (changed) {
				this.fetchRooms()
			}
		}
	},
	async created() {
		await this.ensureConnectedAndFetch()
	},
	beforeUnmount() {
		if (this._unwatchConnected) this._unwatchConnected()
	},
	computed: {
		...mapGetters(['eventRouting', 'hasPermission']),
		canExportBroadcastConfiguration() {
			return this.hasPermission('room:update') && this.eventRouting.organizer && this.eventRouting.event
		}
	},
	methods: {
		exportUrl(format) {
			const organizer = encodeURIComponent(this.eventRouting.organizer)
			const event = encodeURIComponent(this.eventRouting.event)
			return `/api/v1/organizers/${organizer}/events/${event}/rooms/export-broadcast-configuration/?_format=${encodeURIComponent(format)}`
		},
		visibleRooms(rooms) {
			return rooms.filter(room => !isChatManagedRoom(room))
		},
		isRoomVisible(room) {
			if (!this.search) return true
			const search = this.search.trim()
			return String(room.id) === search || fuzzysearch(this.search.toLowerCase(), this.$localize(room.name).toLowerCase())
		},
		async ensureConnectedAndFetch() {
			if (this.$store.state.connected) return this.fetchRooms()
			this._unwatchConnected = this.$store.watch(
				state => state.connected,
				(connected) => {
					if (connected) {
						if (this._unwatchConnected) this._unwatchConnected()
						this._unwatchConnected = null
						this.fetchRooms()
					}
				}
			)
		},
		async fetchRooms() {
			try {
				this.error = null
				this.errorCode = null
				const listed = await api.call('room.config.list')
				this.allRooms = listed
				this.rooms = this.visibleRooms(listed)
			} catch (e) {
				this.error = e
				this.errorCode = e?.code || e?.message || String(e)
				console.error(e)
			}
		},
		createRoomWithProvider(provider) {
			this.$router.push({name: 'admin:rooms:new', params: {type: provider.roomTypeId}})
		},
		async onListSort(newList) {
			if (this.search) return
			const previousRooms = [...this.rooms]
			const previousAll = [...this.allRooms]
			const orderedIds = mergeReorderedIds(
				this.allRooms.map(room => room.id),
				newList.map(room => room.id)
			)
			const byId = Object.fromEntries(this.allRooms.map(room => [String(room.id), room]))
			try {
				this.allRooms = orderedIds.map(id => byId[String(id)])
				this.rooms = this.visibleRooms(this.allRooms)
				await api.call('room.config.reorder', orderedIds)
			} catch (e) {
				this.rooms = previousRooms
				this.allRooms = previousAll
				console.error(e)
			}
		},
		getRoomTargetRoute(room) {
			if (!room) return { name: 'admin:rooms:index' }
			// room.config.list rooms use module_config array (admin config format)
			const isConfigured = Array.isArray(room.module_config) && room.module_config.length > 0 &&
				!!inferType({ module_config: room.module_config })
			if (isConfigured) {
				return { name: 'room:manage', params: { roomId: room.id } }
			}
			return { name: 'admin:rooms:item', params: { roomId: room.id } }
		}
	}
}
</script>
<style lang="stylus">
@import 'flex-table'

.c-admin-rooms
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
			.c-video-provider-dropdown
				margin-right: 0
		.export-actions
			display: flex
			align-items: center
			.export-button
				display: inline-flex
				align-items: center
				height: 32px
				padding: 0 12px
				margin-right: 8px
				border-radius: 3px
				background-color: $clr-primary
				color: $clr-white
				font-size: 13px
				font-weight: 500
				text-decoration: none
				&.secondary
					background-color: transparent
					color: $clr-primary
				&:focus
					outline: 2px solid $clr-primary
					outline-offset: 2px
		.search
			input-style(size: compact)
			padding: 0
			margin: 0
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

.sorting-helper
	height: 48px
	line-height: 48px
	background-color: $clr-white
	box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15)
	cursor: grabbing
	z-index: 9999
	> *
		padding: 0 24px
</style>

<template lang="pug">
.c-admin-chat
	.ui-page-header
		bunt-icon-button(@click="$router.push({name: 'organizer'})", :tooltip="$t('Back to Overview')", tooltip-placement="bottom-start", :tooltip-fixed="true") arrow-left
		h2 {{ $t('Chat Channels') }}
		.actions
			bunt-link-button.btn-create(
				v-if="canCreate",
				:to="{name: 'admin:chat:new'}"
			) {{ $t('Create a new channel') }}
			bunt-input.search(name="search", :placeholder="$t('Search channels')", icon="search", v-model="search")
	.error(v-if="error")
		span {{ $t('Failed to load chat channels.') }}
		span(v-if="errorCode")  ({{ errorCode }})
		span(v-if="errorCode === 'protocol.denied'")  {{ $t('You likely lack admin permissions.') }}
	.rooms-list(v-else)
		.header
			.drag
			.name {{ $t('Name') }}
		SlickList.tbody(v-if="channels", v-model:list="channels", lockAxis="y", :useDragHandle="true", helperClass="sorting-helper", v-scrollbar.y="", @update:list="onListSort")
			RoomListItem(
				v-for="(room, index) of channels",
				:index="index",
				:key="room.id",
				:room="room",
				:to="{name: 'admin:chat:item', params: {roomId: room.id}}",
				:disabled="!!search",
				v-show="isChannelVisible(room)"
			)
		bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import api from 'lib/api'
import fuzzysearch from 'lib/fuzzysearch'
import { isChatManagedRoom, mergeReorderedIds } from 'lib/room-types'
import { mapGetters } from 'vuex'
import { SlickList } from 'vue-slicksort'
import RoomListItem from 'views/admin/rooms/RoomListItem'

export default {
	name: 'AdminChat',
	components: { SlickList, RoomListItem },
	data() {
		return {
			allRooms: null,
			channels: null,
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
				this.fetchChannels()
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
		...mapGetters(['hasPermission']),
		canCreate() {
			return this.hasPermission('world:rooms.create.chat')
		}
	},
	methods: {
		visibleChannels(rooms) {
			return rooms.filter(room => isChatManagedRoom(room))
		},
		isChannelVisible(room) {
			if (!this.search) return true
			const search = this.search.trim()
			return String(room.id) === search || fuzzysearch(this.search.toLowerCase(), this.$localize(room.name).toLowerCase())
		},
		async ensureConnectedAndFetch() {
			if (this.$store.state.connected) return this.fetchChannels()
			this._unwatchConnected = this.$store.watch(
				state => state.connected,
				(connected) => {
					if (connected) {
						if (this._unwatchConnected) this._unwatchConnected()
						this._unwatchConnected = null
						this.fetchChannels()
					}
				}
			)
		},
		async fetchChannels() {
			try {
				this.error = null
				this.errorCode = null
				const listed = await api.call('room.config.list')
				this.allRooms = listed
				this.channels = this.visibleChannels(listed)
			} catch (e) {
				this.error = e
				this.errorCode = e?.code || e?.message || String(e)
				console.error(e)
			}
		},
		async onListSort(newList) {
			if (this.search) return
			const previousChannels = [...this.channels]
			const previousAll = [...this.allRooms]
			const orderedIds = mergeReorderedIds(
				this.allRooms.map(room => room.id),
				newList.map(room => room.id)
			)
			const byId = Object.fromEntries(this.allRooms.map(room => [String(room.id), room]))
			try {
				this.allRooms = orderedIds.map(id => byId[String(id)])
				this.channels = this.visibleChannels(this.allRooms)
				await api.call('room.config.reorder', orderedIds)
			} catch (e) {
				this.channels = previousChannels
				this.allRooms = previousAll
				console.error(e)
			}
		}
	}
}
</script>
<style lang="stylus">
@import 'flex-table'

.c-admin-chat
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
	.rooms-list
		flex-table()
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

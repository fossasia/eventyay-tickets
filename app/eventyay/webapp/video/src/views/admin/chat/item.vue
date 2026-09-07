<template lang="pug">
.c-admin-chat-item
	.error(v-if="error && !currentRoom")
		span {{ $t('We could not fetch the current configuration.') }}
		span(v-if="errorCode")  ({{ errorCode }})
		span(v-if="errorCode === 'protocol.denied'")  {{ $t('You likely lack admin permissions.') }}
	template(v-else-if="currentRoom")
		.ui-page-header
			bunt-icon-button(@click="$router.push({name: 'admin:chat:index'})", :tooltip="$t('Back to Chat Channels')", tooltip-placement="bottom-start", :tooltip-fixed="true") arrow-left
			h1 {{ inferredType ? inferredType.name : $t('Channel') }} :
				span.room-name(v-html="$emojify(currentRoom.name)")
			.actions
				bunt-button.btn-edit-settings(v-if="hasPermission('room:update')", @click="showRoomEditPrompt = true")
					i.mdi.mdi-cog-outline
					span {{ $t('Edit Settings') }}
		.main-chat(v-if="chatModule")
			chat(:room="currentRoom", :module="chatModule", mode="standalone", :key="roomId")
	bunt-progress-circular(v-else, size="huge")
	transition(name="prompt")
		RoomEditPrompt(
			v-if="showRoomEditPrompt",
			mode="chat",
			:room="{id: roomId}",
			@close="closeRoomEditPrompt",
			@deleted="channelDeleted"
		)
</template>
<script>
import { mapGetters } from 'vuex'
import api from 'lib/api'
import Chat from 'components/Chat'
import RoomEditPrompt from 'components/RoomEditPrompt'
import { inferType, inferRoomType, isChatManagedRoom, localizeRoomType } from 'lib/room-types'

export default {
	name: 'AdminChatItem',
	components: { Chat, RoomEditPrompt },
	props: {
		roomId: String
	},
	data() {
		return {
			error: null,
			errorCode: null,
			config: null,
			showRoomEditPrompt: false,
			_unwatchConnected: null
		}
	},
	computed: {
		...mapGetters(['hasPermission']),
		room() {
			const wantedId = String(this.roomId)
			return this.$store.state.rooms?.find(r => String(r.id) === wantedId || (r.pretalx_id != null && String(r.pretalx_id) === wantedId))
		},
		currentRoom() {
			return this.room || this.config
		},
		inferredType() {
			if (!this.currentRoom) return null
			const type = this.room ? inferRoomType(this.room) : inferType(this.config)
			return localizeRoomType(this.$t.bind(this), type)
		},
		chatModule() {
			if (this.room?.modules) {
				const m = this.room.modules.find(mod => mod.type === 'chat.native') || this.room.modules[0]
				if (m?.channel_id) return m
			}
			if (this.config?.module_config) {
				const m = this.config.module_config.find(mod => mod.type === 'chat.native') || this.config.module_config[0]
				if (m?.channel_id) return m
			}
			return { channel_id: this.room?.modules?.[0]?.channel_id || this.roomId, type: 'chat.native' }
		}
	},
	watch: {
		roomId: {
			handler() {
				this.config = null
				this.error = null
				this.errorCode = null
				this.ensureConnectedAndFetch()
			}
		}
	},
	async created() {
		await this.ensureConnectedAndFetch()
	},
	beforeUnmount() {
		if (this._unwatchConnected) this._unwatchConnected()
	},
	methods: {
		async ensureConnectedAndFetch() {
			if (this.$store.state.connected) return this.fetchConfig()
			this._unwatchConnected = this.$store.watch(
				state => state.connected,
				(connected) => {
					if (connected) {
						if (this._unwatchConnected) this._unwatchConnected()
						this._unwatchConnected = null
						this.fetchConfig()
					}
				}
			)
		},
		async fetchConfig() {
			try {
				this.error = null
				this.errorCode = null
				this.config = await api.call('room.config.get', {room: this.roomId})
				if (!isChatManagedRoom(this.config) && !isChatManagedRoom(this.room)) {
					this.$router.replace({name: 'admin:rooms:item', params: {roomId: this.roomId}})
				}
			} catch (error) {
				this.error = error
				this.errorCode = error?.code || error?.message || String(error)
				console.error(error)
			}
		},
		closeRoomEditPrompt() {
			this.showRoomEditPrompt = false
			this.fetchConfig()
		},
		channelDeleted() {
			this.$router.replace({name: 'admin:chat:index'})
		}
	}
}
</script>
<style lang="stylus">
.c-admin-chat-item
	display: flex
	flex-direction: column
	background: $clr-white
	min-height: 0
	min-width: 0
	flex: auto
	height: 100%
	.bunt-icon-button
		icon-button-style(style: clear)
	.ui-page-header
		background-color: $clr-grey-100
		display: flex
		align-items: center
		padding: 0 16px
		height: 56px
		flex: none
		.bunt-icon-button
			margin-right: 8px
		h1
			flex: auto
			font-size: 20px
			font-weight: 500
			margin: 0
			ellipsis()
			.room-name
				margin-left: 8px
				font-size: 20px
				font-weight: 600
				.emoji
					display: inline-block
					vertical-align: middle
					width: 28px
					height: @width
					&.needs-space
						margin-right: 8px
		.actions
			display: flex
			align-items: center
			gap: 8px
			flex: none
			.btn-edit-settings
				display: flex
				align-items: center
				gap: 6px
				font-size: 13px
				font-weight: 500
				.mdi
					font-size: 16px
	.main-chat
		flex: auto
		display: flex
		flex-direction: column
		min-height: 0
		min-width: 0
		.c-chat
			flex: auto
			min-height: 0
</style>

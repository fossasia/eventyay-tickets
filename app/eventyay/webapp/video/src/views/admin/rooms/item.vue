<template lang="pug">
.c-admin-room
	.error(v-if="error")
		span {{ $t('We could not fetch the current configuration.') }}
		span(v-if="errorCode")  ({{ errorCode }})
		span(v-if="errorCode === 'protocol.denied'")  {{ $t('You likely lack admin permissions.') }}
	template(v-else-if="config")
		template(v-if="!inferredType")
			.ui-page-header
				bunt-icon-button(@click="$router.push({name: 'admin:rooms:index'})", :tooltip="$t('Back to Rooms & Stages')", tooltip-placement="bottom-start", :tooltip-fixed="true") arrow-left
				h1(v-html="$emojify(config.name)")
			.mystery-room
				p {{ $t('This room does not have a video option yet.') }}
				VideoProviderDropdown(:label="$t('Add Video')", variant="action", @select="addVideoProvider")
		template(v-else)
			.ui-page-header
				bunt-icon-button(@click="$router.push({name: 'admin:rooms:index'})", :tooltip="$t('Back to Rooms & Stages')", tooltip-placement="bottom-start", :tooltip-fixed="true") arrow-left
				h1 {{ roomTypeLabel }} :
					span.room-name(v-html="$emojify(config.name)")
			edit-form(:config="config")
	bunt-progress-circular(v-else, size="huge")
</template>
<script>
import { mapGetters } from 'vuex'
import api from 'lib/api'
import VideoProviderDropdown from 'components/VideoProviderDropdown'
import { getRoomTypeById, inferType, isChatManagedRoom } from 'lib/room-types'
import {
	applyVideoProviderToConfig,
	getAvailableVideoProviders,
	getConfiguredRoomLabel,
} from 'lib/video-providers'
import features from 'features'
import EditForm from './EditForm'

export default {
	name: 'AdminRoom',
	components: { EditForm, VideoProviderDropdown },
	props: {
		roomId: String
	},
	data() {
		return {
			error: null,
			errorCode: null,
			config: null,
			_unwatchConnected: null
		}
	},
	computed: {
		...mapGetters(['hasPermission', 'isAdminMode']),
		inferredType() {
			if (!this.config) return null
			return inferType(this.config)
		},
		roomTypeLabel() {
			const label = getConfiguredRoomLabel(this.inferredType)
			return label ? this.$t(label) : ''
		},
		availableProviders() {
			return getAvailableVideoProviders(
				this.hasPermission,
				this.isAdminMode,
				(flag) => features.enabled(flag)
			)
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
			// wait until websocket joined before calling
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
				if (isChatManagedRoom(this.config)) {
					this.$router.replace({name: 'admin:chat:item', params: {roomId: this.roomId}})
					return
				}
				await this.applyProviderFromQuery()
			} catch (error) {
				this.error = error
				this.errorCode = error?.code || error?.message || String(error)
				console.error(error)
			}
		},
		async applyProvider(roomTypeId) {
			if (this.inferredType) return
			if (!this.availableProviders.some(provider => provider.roomTypeId === roomTypeId)) return
			const type = getRoomTypeById(roomTypeId)
			if (!type) return
			const previousModuleConfig = this.config.module_config
			applyVideoProviderToConfig(this.config, type)
			try {
				const updated = await api.call('room.config.patch', {
					room: this.config.id,
					module_config: this.config.module_config
				})
				Object.assign(this.config, updated)
			} catch (error) {
				this.config.module_config = previousModuleConfig
				console.error('Failed to apply video provider: %o', error)
			}
		},
		async applyProviderFromQuery() {
			const roomTypeId = this.$route.query.provider
			if (!roomTypeId) return
			await this.applyProvider(roomTypeId)
			if (this.$route.query.provider) {
				const query = { ...this.$route.query }
				delete query.provider
				this.$router.replace({ query })
			}
		},
		addVideoProvider(provider) {
			return this.applyProvider(provider.roomTypeId)
		},
		roomDeleted() {
			this.$router.replace({name: 'admin:rooms:index'})
		}
	}
}
</script>
<style lang="stylus">
.c-admin-room
	display: flex
	flex-direction: column
	background: $clr-white
	min-height: 0
	min-width: 0
	.bunt-icon-button
		icon-button-style(style: clear)
	.ui-page-header
		background-color: $clr-grey-100
		.bunt-icon-button
			margin-right: 8px
		h1
			flex: auto
			font-size: 24px
			font-weight: 500
			margin: 1px 16px 0 0
			ellipsis()
			.room-name
				margin-left: 8px
				font-size: 24px
				line-height: 56px
				font-weight: 600
				// TODO decopypaste
				.emoji
					display: inline-block
					vertical-align: middle
					width: 36px
					height: @width
					&.needs-space
						margin-right: 8px
		.actions
			display: flex
			flex: none
			.bunt-button:not(:last-child)
				margin-right: 16px
	.mystery-room
		flex: auto
		display: flex
		flex-direction: column
		justify-content: center
		align-items: center
		gap: 12px
		padding: 24px
		p
			margin: 0
			font-size: 16px
			color: $clr-secondary-text-light
</style>

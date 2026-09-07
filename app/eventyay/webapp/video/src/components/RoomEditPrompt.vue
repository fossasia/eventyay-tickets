<template lang="pug">
prompt.c-room-edit-prompt(:scrollable="false", @close="$emit('close')")
	.content
		.prompt-header
			h2 {{ promptTitle }}
		bunt-progress-circular(v-if="loading", size="large")
		.error(v-else-if="error")
			p {{ error }}
			bunt-button(@click="fetchConfig") {{ $t('Retry') }}
		template(v-else-if="config")
			.edit-body(v-scrollbar.y="")
				.reset-section(v-if="wasConfigured && mode !== 'chat'")
					.section-header
						h3 {{ $t('Reset Room') }}
						bunt-button.btn-reset(
							v-if="!confirmingReset",
							@click="confirmingReset = true",
						) {{ $t('Reset') }}
					p {{ $t('Return this room to the unconfigured state. The room itself and assigned sessions stay in place.') }}
					.confirmation(v-if="confirmingReset")
						p {{ $t('Are you sure you want to reset this room to the unconfigured state?') }}
						.confirmation-actions
							bunt-button.btn-cancel(@click="confirmingReset = false") {{ $t('Cancel') }}
							bunt-button.btn-reset(@click="resetRoom", :loading="resetting", :error-message="resetError") {{ $t('Confirm reset') }}
				.type-section(v-if="mode !== 'chat'")
					h3 {{ $t('Video option') }}
					.current-type(v-if="inferredType")
						.mdi(:class="[`mdi-${inferredType.icon}`]")
						span {{ currentTypeLabel }}
					.type-picker
						.type-option(
							v-for="type of availableRoomTypes",
							:key="type.id",
							:class="{active: inferredType && inferredType.id === type.id}",
							@click="changeType(type)"
						)
							.icon.mdi(:class="[`mdi-${type.icon}`]")
							.text
								.name {{ $t(type.name) }}
								.description {{ $t(type.description) }}
				.generic-settings
					bunt-input(name="name", v-model="localizedName", :label="$t('Name')")
					bunt-input(name="description", v-model="localizedDescription", :label="$t('Description')")
				component.type-settings(
					ref="settings",
					v-if="inferredType && typeComponents[inferredType.id]",
					:key="inferredType.id",
					:is="typeComponents[inferredType.id]",
					:config="config",
					:modules="modules",
					:creating="!wasConfigured"
				)
				sidebar-addons(
					v-if="inferredType && (inferredType.id === 'stage' || inferredType.id === 'channel-janus' || inferredType.id === 'channel-zoom')",
					:config="config",
					:modules="modules",
					:creating="!wasConfigured"
				)
				.danger-zone(v-if="wasConfigured && hasPermission('room:delete')")
					h3 {{ $t('Danger Zone') }}
					p(v-if="mode === 'chat'") {{ $t('Deleting this channel removes it for attendees. Messages and calls in this channel will no longer be available.') }}
					p(v-else) {{ $t('Deleting this room will remove it from the schedule, but the sessions will remain safe.') }} {{ $t('Sessions assigned to this room will no longer have a room assigned.') }}
					bunt-button.btn-delete-room(v-if="!confirmingDelete", @click="confirmingDelete = true") {{ $t('Delete') }}
					.delete-confirmation(v-else)
						p {{ $t('Please type') }} #[b {{ localizedRoomName }}] {{ $t('to confirm deletion.') }}
						bunt-input(name="deletingRoomName", :label="mode === 'chat' ? $t('Channel name') : $t('Room name')", v-model="deletingRoomName", @keypress.enter="deleteRoom")
						.confirmation-actions
							bunt-button.btn-cancel(@click="cancelDelete") {{ $t('Cancel') }}
							bunt-button.btn-delete-room(icon="delete", :disabled="deletingRoomName !== localizedRoomName", @click="deleteRoom", :loading="deleting", :error-message="deleteError") {{ mode === 'chat' ? $t('Delete this channel') : $t('Delete this room') }}
			.edit-actions
				bunt-button.btn-cancel(@click="$emit('close')") {{ $t('Cancel') }}
				bunt-button.btn-save(@click="save", :loading="saving", :error-message="saveError") {{ $t('Save') }}
</template>
<script>
import { markRaw } from 'vue'
import { mapGetters } from 'vuex'
import api from 'lib/api'
import Prompt from 'components/Prompt'
import { getRoomTypeById, inferType } from 'lib/room-types'
import {
	getAvailableVideoProviders,
	getConfiguredRoomLabel,
	applyVideoProviderToConfig,
} from 'lib/video-providers'
import features from 'features'
import Stage from 'views/admin/rooms/types-edit/stage'
import ChannelBBB from 'views/admin/rooms/types-edit/channel-bbb'
import ChannelJanus from 'views/admin/rooms/types-edit/channel-janus'
import ChannelJitsi from 'views/admin/rooms/types-edit/channel-jitsi'
import ChannelZoom from 'views/admin/rooms/types-edit/channel-zoom'
import ChannelRoulette from 'views/admin/rooms/types-edit/channel-roulette'
import PageLanding from 'views/admin/rooms/types-edit/page-landing'
import SidebarAddons from 'views/admin/rooms/types-edit/SidebarAddons'
import {
	cloneLanguageStreamEntries,
	fetchInterpretationLanguageStreams,
	saveInterpretationLanguageStreams,
} from 'lib/interpretation-language-streams'

export default {
	components: { Prompt, SidebarAddons },
	provide () {
		return {
			interpretationAdmin: this.interpretationAdmin,
		}
	},
	props: {
		room: {
			type: Object,
			required: true
		},
		mode: {
			type: String,
			default: 'room'
		}
	},
	emits: ['close', 'deleted'],
	data () {
		return {
			loading: true,
			error: null,
			config: null,
			wasConfigured: false,
			saving: false,
			saveError: null,
			confirmingReset: false,
			resetting: false,
			resetError: null,
			confirmingDelete: false,
			deletingRoomName: '',
			deleting: false,
			deleteError: null,
			interpretationAdmin: {
				usePluginStreams: false,
				languageStreams: [],
				loaded: false,
				streamsLoadFailed: false,
			},
			typeComponents: markRaw({
				stage: Stage,
				'page-landing': PageLanding,
				'channel-bbb': ChannelBBB,
				'channel-roulette': ChannelRoulette,
				'channel-janus': ChannelJanus,
				'channel-jitsi': ChannelJitsi,
				'channel-zoom': ChannelZoom,
			})
		}
	},
	computed: {
		...mapGetters(['hasPermission', 'isAdminMode']),
		availableRoomTypes () {
			const videoTypes = getAvailableVideoProviders(
				this.hasPermission,
				this.isAdminMode,
				(flag) => features.enabled(flag),
				this.$store.state.world?.video_providers
			).map(provider => {
				const type = getRoomTypeById(provider.roomTypeId)
				if (!type) return null
				return {
					...type,
					name: provider.label,
					description: provider.description
				}
			}).filter(Boolean)
			if (this.inferredType && !videoTypes.some(type => type.id === this.inferredType.id)) {
				return [this.inferredType, ...videoTypes]
			}
			return videoTypes
		},
		modules () {
			if (!this.config) return {}
			return this.config.module_config.reduce((acc, module) => {
				acc[module.type] = module
				return acc
			}, {})
		},
		inferredType () {
			if (!this.config) return null
			return inferType(this.config)
		},
		promptTitle () {
			if (this.mode !== 'chat') return this.$t('Edit Room')
			return this.$t('Edit Chat Channel')
		},
		localizedName: {
			get () {
				return this.$localize(this.config.name)
			},
			set (value) {
				this.config.name = value
			}
		},
		localizedDescription: {
			get () {
				return this.$localize(this.config.description)
			},
			set (value) {
				this.config.description = value
			}
		},
		localizedRoomName () {
			return this.$localize(this.config?.name)
		},
		currentTypeLabel () {
			const label = getConfiguredRoomLabel(this.inferredType)
			return label ? this.$t(label) : ''
		}
	},
	async created () {
		await this.fetchConfig()
		await this.loadInterpretationLanguageStreams()
	},
	methods: {
		async fetchConfig () {
			this.loading = true
			this.error = null
			try {
				this.config = await api.call('room.config.get', { room: this.room.id })
				this.wasConfigured = !!inferType(this.config)
			} catch (err) {
				this.error = err.code === 'protocol.denied'
					? this.$t('You do not have permission to edit this room.')
					: (err.message || String(err))
			} finally {
				this.loading = false
			}
		},
		async loadInterpretationLanguageStreams () {
			if (!this.config?.id) return
			this.interpretationAdmin.streamsLoadFailed = false
			try {
				const data = await fetchInterpretationLanguageStreams(
					this.$store,
					this.config.id
				)
				this.interpretationAdmin.usePluginStreams = Boolean(
					data.use_plugin_language_streams
				)
				this.config.interpretation_use_plugin_streams = this.interpretationAdmin.usePluginStreams
				if (this.interpretationAdmin.usePluginStreams) {
					this.interpretationAdmin.languageStreams = cloneLanguageStreamEntries(
						data.language_streams
					)
				}
			} catch (error) {
				console.warn('interpretation language streams unavailable', error)
				this.interpretationAdmin.streamsLoadFailed = true
				this.interpretationAdmin.usePluginStreams = Boolean(
					this.config.interpretation_use_plugin_streams
				)
				this.interpretationAdmin.languageStreams = []
			} finally {
				this.interpretationAdmin.loaded = true
			}
		},
		changeType (type) {
			if (this.inferredType && this.inferredType.id === type.id) return
			applyVideoProviderToConfig(this.config, type)
		},
		async resetRoom () {
			this.resetError = null
			this.resetting = true
			try {
				await api.call('room.config.patch', {
					room: this.config.id,
					module_config: []
				})
				this.$emit('close')
			} catch (err) {
				console.error('Failed to reset room: %o', err)
				this.resetError = err.message || String(err)
			} finally {
				this.resetting = false
			}
		},
		cancelDelete () {
			this.confirmingDelete = false
			this.deletingRoomName = ''
			this.deleteError = null
		},
		async deleteRoom () {
			if (this.deletingRoomName !== this.localizedRoomName) return
			this.deleteError = null
			this.deleting = true
			try {
				await api.call('room.delete', { room: this.config.id })
				this.$emit('deleted')
			} catch (err) {
				console.error('Failed to delete room: %o', err)
				this.deleteError = err.message || String(err)
			} finally {
				this.deleting = false
			}
		},
		async save () {
			this.saveError = null
			this.$refs.settings?.beforeSave?.()
			this.saving = true
			try {
				const roomId = this.config.id
				let moduleConfig = this.config.module_config || []
				if (this.inferredType?.videoChannel) {
					moduleConfig = moduleConfig.filter(
						m => !['chat.native', 'question', 'poll'].includes(m.type)
					)
				}
				await api.call('room.config.patch', {
					room: roomId,
					name: this.config.name,
					description: this.config.description,
					picture: this.config.picture,
					force_join: this.config.force_join,
					module_config: moduleConfig
				})
				if (this.$refs.settings?.saveStreamSchedules) {
					await this.$refs.settings.saveStreamSchedules(roomId)
				}
				if (
					this.interpretationAdmin.usePluginStreams &&
					roomId &&
					this.interpretationAdmin.loaded &&
					!this.interpretationAdmin.streamsLoadFailed
				) {
					await saveInterpretationLanguageStreams(
						this.$store,
						roomId,
						this.interpretationAdmin.languageStreams
					)
				}
				this.saving = false
				this.$emit('close')
			} catch (err) {
				this.saving = false
				this.saveError = err.message || String(err)
			}
		}
	}
}
</script>
<style lang="stylus">
.c-room-edit-prompt
	.prompt-wrapper
		width: 640px
		max-width: 90vw
		max-height: 85vh
		display: flex
		flex-direction: column
	.content
		display: flex
		flex-direction: column
		min-height: 0
		flex: auto
	.prompt-header
		padding: 16px 16px 0
		h2
			margin: 0
			font-size: 20px
			font-weight: 600
	.edit-body
		flex: auto
		min-height: 0
		padding: 16px
		display: flex
		flex-direction: column
		gap: 16px
	.reset-section
		padding: 12px
		border: border-separator()
		border-radius: 4px
		background-color: $clr-grey-50
		p
			margin: 0
			font-size: 13px
			line-height: 18px
			color: $clr-secondary-text-light
	.section-header
		display: flex
		align-items: center
		justify-content: space-between
		gap: 12px
		h3
			margin: 0
			font-size: 16px
			font-weight: 500
	.confirmation
		margin-top: 12px
		padding-top: 12px
		border-top: border-separator()
	.confirmation-actions
		display: flex
		justify-content: flex-end
		gap: 8px
		margin-top: 12px
	.btn-reset
		button-style(color: $clr-orange)
	.type-section
		h3
			margin: 0 0 8px
			font-size: 16px
			font-weight: 500
		.current-type
			display: flex
			align-items: center
			gap: 8px
			margin-bottom: 12px
			font-size: 14px
			color: $clr-secondary-text-light
			.mdi
				font-size: 20px
	.type-picker
		display: flex
		flex-direction: column
		border: border-separator()
		border-radius: 4px
		.type-option
			display: flex
			align-items: center
			padding: 8px 12px
			cursor: pointer
			transition: background-color 0.15s
			&:not(:last-child)
				border-bottom: border-separator()
			&:hover
				background-color: $clr-grey-50
			&.active
				background-color: var(--clr-primary-light, $clr-blue-50)
				border-left: 3px solid var(--clr-primary)
				padding-left: 9px
			.icon
				font-size: 24px
				margin-right: 10px
				flex: none
			.text
				display: flex
				flex-direction: column
			.name
				font-size: 14px
				line-height: 20px
				font-weight: 500
			.description
				font-size: 12px
				color: $clr-secondary-text-light
				line-height: 16px
	.generic-settings
		display: flex
		flex-direction: column
		gap: 8px
	.type-settings
		margin-top: 8px
	.danger-zone
		padding: 12px
		border: 1px solid $clr-danger
		border-radius: 4px
		background-color: rgba($clr-danger, 0.05)
		h3
			margin: 0 0 8px
			font-size: 16px
			font-weight: 600
			color: $clr-danger
		p
			margin: 0 0 12px
			font-size: 13px
			line-height: 18px
	.delete-confirmation
		margin-top: 12px
		padding-top: 12px
		border-top: border-separator()
	.btn-delete-room
		button-style(color: $clr-danger)
	.edit-actions
		display: flex
		justify-content: flex-end
		gap: 8px
		padding: 12px 16px
		border-top: border-separator()
		.btn-cancel
			themed-button-secondary()
		.btn-save
			themed-button-primary()
</style>

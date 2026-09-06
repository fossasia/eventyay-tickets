<template lang="pug">
.c-room-edit-form
	.scroll-wrapper(v-scrollbar.y="")
		.ui-form-body
			.generic-settings
				.room-info-card
					.form-grid
						.field-group.name-field
							label.field-label
								| {{ $t('Name') }}
								span.required-star *
							.input-wrapper
								input.text-input(
									type="text"
									v-model="localizedName"
									:placeholder="$t('e.g. Main Stage')"
									:class="{'has-error': v$.config.name.$error}"
								)
							.field-error(v-if="v$.config.name.$error")
								| {{ v$.config.name.$errors[0]?.$message || $t('Name is required') }}

						.field-group.desc-field
							label.field-label
								| {{ $t('Description') }}
							.input-wrapper
								input.text-input(
									type="text"
									v-model="localizedDescription"
									:placeholder="$t('Optional short description for attendees')"
								)

					.unscheduled-setting-row(v-if="!isChat", :title="unscheduledDisabledTitle", :class="{'is-disabled': config.has_linked_sessions}")
						.setting-text
							.setting-title {{ $t('Unscheduled room') }}
							.setting-desc {{ $t('Hide this room from the event schedule and public session listings.') }}
						.setting-control
							bunt-switch(
								name="is_unscheduled"
								v-model="config.is_unscheduled"
								:disabled="config.has_linked_sessions"
							)

					template(v-if="isChat")
						.force-join-setting-row
							.setting-text
								.setting-title {{ $t('Force join on login') }}
								.setting-desc {{ $t('Automatically join attendees to this chat on login (use for text-based chats only).') }}
							.setting-control
								bunt-switch(name="force_join", v-model="config.force_join")

			component.stage-settings(ref="settings", v-if="inferredType && typeComponents[inferredType.id]", :is="typeComponents[inferredType.id]", :config="config", :modules="modules", :creating="creating")
			sidebar-addons(v-if="inferredType && inferredType.id === 'stage'", :config="config", :modules="modules", :creating="creating")
	.ui-form-actions
		bunt-button.btn-save(@click="save", :loading="saving", :error="!!error") {{ creating ? $t('Create') : $t('Save') }}
		bunt-button.btn-sync(v-if="!creating && interpretationAdmin.usePluginStreams", @click="syncServices", :loading="syncing", :error="!!syncError", style="margin-left: 10px") {{ $t('Sync Services') }}
		.errors {{ error || syncError || validationErrors.join(', ') }}
</template>
<script>
import { markRaw } from 'vue'
import { useVuelidate } from '@vuelidate/core'
import { mapGetters } from 'vuex'
import api from 'lib/api'
import { required } from 'lib/validators'
import ValidationErrorsMixin from 'components/mixins/validation-errors'
import ROOM_TYPES, { inferType, isChatChannel } from 'lib/room-types'
import { filterRoomTypesByPermission } from 'lib/room-type-permissions'
import Stage from './types-edit/stage'
import ChannelBBB from './types-edit/channel-bbb'
import ChannelJanus from './types-edit/channel-janus'
import ChannelJitsi from './types-edit/channel-jitsi'
import ChannelZoom from './types-edit/channel-zoom'
import ChannelRoulette from './types-edit/channel-roulette'
import PageLanding from './types-edit/page-landing'
import SidebarAddons from './types-edit/SidebarAddons'
import {
	cloneLanguageStreamEntries,
	fetchInterpretationLanguageStreams,
	saveInterpretationLanguageStreams,
	syncInterpretationServices,
} from 'lib/interpretation-language-streams'

export default {
	components: { SidebarAddons },
	mixins: [ValidationErrorsMixin],
	provide() {
		return {
			interpretationAdmin: this.interpretationAdmin,
		}
	},
	props: {
		config: {
			type: Object,
			required: true
		},
		creating: {
			type: Boolean,
			default: false
		}
	},
	setup:() => ({v$:useVuelidate()}),
	data() {
		return {
			allRoomTypes: ROOM_TYPES,
			typeComponents: markRaw({
				stage: Stage,
				'page-landing': PageLanding,
				'channel-bbb': ChannelBBB,
				'channel-roulette': ChannelRoulette,
				'channel-janus': ChannelJanus,
				'channel-jitsi': ChannelJitsi,
				'channel-zoom': ChannelZoom,
			}),
			saving: false,
			syncing: false,
			error: null,
			syncError: null,
			interpretationAdmin: {
				usePluginStreams: false,
				languageStreams: [],
				loaded: false,
				streamsLoadFailed: false,
			},
		}
	},
	async created() {
		await this.loadInterpretationLanguageStreams()
	},
	computed: {
		...mapGetters(['hasPermission', 'isAdminMode']),
		availableRoomTypes() {
			return filterRoomTypesByPermission(this.allRoomTypes, this.hasPermission, this.isAdminMode)
		},
		modules() {
			return this.config?.module_config.reduce((acc, module) => {
				acc[module.type] = module
				return acc
			}, {})
		},
		inferredType() {
			return inferType(this.config)
		},
		isChat() {
			return isChatChannel(this.config)
		},
		unscheduledDisabledTitle() {
			this.$store.state.userLocale
			if (!this.config.has_linked_sessions) return ''
			return this.$t('Room has linked sessions and cannot be marked unscheduled')
		},
		localizedName: {
			get() {
				return this.$localize(this.config.name)
			},
			set(value) {
				this.config.name = value
			}
		},
		localizedDescription: {
			get() {
				return this.$localize(this.config.description)
			},
			set(value) {
				this.config.description = value
			}
		}
	},
	validations() {
		return {
			config: {
				name: {
					required: required(this.$t('name is required'))
				},
			},
		}
	},
	methods: {
		async loadInterpretationLanguageStreams() {
			if (this.creating || !this.config?.id) return
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
		async save({ openScheduleAfterCreate = false, streamScheduleDraft = null } = {}) {
			this.error = null
			this.v$.$touch()
			if (this.v$.$invalid) return

			if (this.$refs.settings?.validate && !this.$refs.settings.validate()) {
				return
			}

			this.$refs.settings?.beforeSave?.()
			this.saving = true
			try {
				let roomId = this.config.id
				if (this.creating) {
					({ room: roomId } = await this.$store.dispatch('createRoom', {
						name: this.config.name,
						description: this.config.description,
						modules: []
					}))
				}
				const updated = await api.call('room.config.patch', {
					room: roomId,
					name: this.config.name,
					description: this.config.description,
					picture: this.config.picture,
					force_join: this.config.force_join,
					is_unscheduled: this.config.is_unscheduled,
					module_config: this.config.module_config,
				})
				Object.assign(this.config, updated)

				if (openScheduleAfterCreate && streamScheduleDraft) {
					sessionStorage.setItem(`streamScheduleDraft:${roomId}`, JSON.stringify(streamScheduleDraft))
				}

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
				if (this.creating) {
					const routeName = this.isChat ? 'admin:chat:item' : 'admin:rooms:item'
					const query = openScheduleAfterCreate ? { schedule: 'new' } : {}
					this.$router.push({
						name: routeName,
						params: {roomId},
						query
					})
				}
			} catch (error) {
				console.error(error)
				this.saving = false
				this.error = error.message || error
			}
		},
		async syncServices() {
			this.syncError = null
			this.syncing = true
			try {
				await syncInterpretationServices(this.$store, this.config.id)
			} catch (error) {
				this.syncError = error.message || error
			}
			this.syncing = false
		},
		clearOpenStreamScheduleCreateQuery() {
			if (this.$route.query.schedule !== 'new') return
			const query = { ...this.$route.query }
			delete query.schedule
			this.$router.replace({ query })
		},
		createRoomForStreamSchedule(streamScheduleDraft) {
			return this.save({ openScheduleAfterCreate: true, streamScheduleDraft })
		}
	}
}
</script>
<style lang="stylus">
.c-room-edit-form
	flex: auto
	min-height: 0
	height: 100vh
	display: flex
	flex-direction: column
	.scroll-wrapper
		flex: auto
		min-height: 0
		display: flex
		flex-direction: column

	.generic-settings
		margin-bottom: 20px
		.room-info-card
			background: #ffffff
			border: 1px solid $clr-grey-200
			border-radius: 8px
			box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04)
			padding: 16px
			display: flex
			flex-direction: column
			gap: 16px

		.form-grid
			display: grid
			grid-template-columns: minmax(200px, 300px) 1fr
			gap: 16px
			@media (max-width: 640px)
				grid-template-columns: 1fr

		.field-group
			display: flex
			flex-direction: column
			gap: 6px
			.field-label
				font-size: 13px
				font-weight: 500
				color: $clr-grey-700
				.required-star
					color: $clr-danger

		.input-wrapper
			.text-input
				width: 100%
				height: 40px
				padding: 0 12px
				border: 1px solid $clr-grey-300
				border-radius: 6px
				font-size: 14px
				font-family: inherit
				background: #ffffff
				color: $clr-grey-800
				box-sizing: border-box
				outline: none
				transition: border-color 0.15s ease, box-shadow 0.15s ease
				&:focus
					border-color: var(--clr-primary)
					box-shadow: 0 0 0 2px rgba(187, 0, 17, 0.15)
				&.has-error
					border-color: $clr-danger

		.field-error
			font-size: 12px
			color: $clr-danger
			margin-top: 2px

		.unscheduled-setting-row, .force-join-setting-row
			display: flex
			align-items: center
			justify-content: space-between
			padding-top: 14px
			border-top: 1px solid $clr-grey-100
			gap: 16px
			&.is-disabled
				opacity: 0.6
				cursor: not-allowed
			.setting-text
				display: flex
				flex-direction: column
				gap: 2px
				.setting-title
					font-size: 14px
					font-weight: 500
					color: $clr-grey-900
				.setting-desc
					font-size: 13px
					color: $clr-secondary-text-light
					line-height: 18px
			.setting-control
				flex-shrink: 0
				.bunt-switch
					margin: 0
</style>

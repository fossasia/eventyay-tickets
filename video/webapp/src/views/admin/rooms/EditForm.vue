<template lang="pug">
.c-room-edit-form
	.scroll-wrapper(v-scrollbar.y="")
		.ui-form-body
			.generic-settings
				bunt-input(name="name", v-model="config.name", label="Name", :validation="$v.config.name")
				bunt-input(name="description", v-model="config.description", label="Description")
				bunt-input(name="sorting_priority", v-model="config.sorting_priority", label="Sorting priority", :validation="$v.config.sorting_priority")
				bunt-input(v-if="inferredType.id === 'stage'", name="pretalx_id", v-model="config.pretalx_id", label="pretalx ID", :validation="$v.config.pretalx_id")
				bunt-checkbox(v-if="['channel-text', 'channel-bbb', , 'channel-janus'].includes(inferredType.id)", name="force_join", v-model="config.force_join", label="Force join on login (use for non-volatile, text-based chats only!!)")
			component.stage-settings(v-if="typeComponents[inferredType.id]", :is="typeComponents[inferredType.id]", :config="config", :modules="modules")
	.ui-form-actions
		bunt-button.btn-save(@click="save", :loading="saving", :error-message="error") {{ creating ? 'create' : 'save' }}
		.errors {{ validationErrors.join(', ') }}
</template>
<script>
import api from 'lib/api'
import Prompt from 'components/Prompt'
import { required, integer } from 'lib/validators'
import ValidationErrorsMixin from 'components/mixins/validation-errors'
import { inferType } from './room-types'
import Stage from './types-edit/stage'
import PageStatic from './types-edit/page-static'
import PageIframe from './types-edit/page-iframe'
import ChannelBBB from './types-edit/channel-bbb'
import ChannelZoom from './types-edit/channel-zoom'

export default {
	components: { Prompt },
	mixins: [ValidationErrorsMixin],
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
	data () {
		return {
			typeComponents: {
				stage: Stage,
				'page-static': PageStatic,
				'page-iframe': PageIframe,
				'channel-bbb': ChannelBBB,
				'channel-zoom': ChannelZoom
			},
			saving: false,
			error: null
		}
	},
	computed: {
		modules () {
			return this.config?.module_config.reduce((acc, module) => {
				acc[module.type] = module
				return acc
			}, {})
		},
		inferredType () {
			return inferType(this.config)
		}
	},
	validations () {
		const config = {
			name: {
				required: required('name is required')
			},
			sorting_priority: {
				integer: integer('sorting priority must be a number')
			},
			pretalx_id: {
				integer: integer('pretalx id must be a number')
			},
		}

		if (!this.creating) config.sorting_priority.required = required('sorting priority is required')

		return { config }
	},
	methods: {
		async save () {
			this.error = null
			this.$v.$touch()
			if (this.$v.$invalid) return
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
				await api.call('room.config.patch', {
					room: roomId,
					name: this.config.name,
					description: this.config.description,
					sorting_priority: this.config.sorting_priority === '' ? undefined : this.config.sorting_priority,
					pretalx_id: this.config.pretalx_id || 0, // TODO weird default
					picture: this.config.picture,
					force_join: this.config.force_join,
					module_config: this.config.module_config,
				})
				this.saving = false
				if (this.creating) {
					this.$router.push({name: 'admin:rooms:item', params: {roomId}})
				}
			} catch (error) {
				console.error(error)
				this.saving = false
				this.error = error.message || error
			}
		}
	}
}
</script>
<style lang="stylus">
.c-room-edit-form
	flex: auto
	min-height: 0
	display: flex
	flex-direction: column
	.scroll-wrapper
		flex: auto
		display: flex
		flex-direction: column
</style>

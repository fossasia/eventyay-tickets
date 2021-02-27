<template lang="pug">
.c-room-edit-form
	bunt-tabs
		bunt-tab(id="main", header="Content", v-scrollbar.y="")
			.form-wrapper
				.generic-settings
					bunt-input(name="name", v-model="config.name", label="Name", :validation="$v.config.name")
					bunt-input(name="description", v-model="config.description", label="Description")
					bunt-input(name="sorting_priority", v-model="config.sorting_priority", label="Sorting priority", :validation="$v.config.sorting_priority")
					bunt-input(v-if="inferredType.id === 'stage'", name="pretalx_id", v-model="config.pretalx_id", label="pretalx ID", :validation="$v.config.pretalx_id")
					bunt-checkbox(v-if="['channel-text', 'channel-video'].includes(inferredType.id)", name="force_join", v-model="config.force_join", label="Force join on login (use for non-volatile, text-based chats only!!)")
				component.stage-settings(v-if="typeComponents[inferredType.id]", :is="typeComponents[inferredType.id]", :config="config", :modules="modules")
		bunt-tab.raw-config(id="advanced", header="Raw Config")
			bunt-input-outline-container(label="Raw config")
				textarea(v-model="rawConfig", slot-scope="{focus, blur}", @focus="focus", @blur="blur")
			.raw-config-error {{ rawConfigError }}
	.form-actions
		bunt-button.btn-save(@click="save", :loading="saving", :error-message="error") {{ creating ? 'create' : 'save' }}
		.errors {{ errors.join(', ') }}
</template>
<script>
import api from 'lib/api'
import Prompt from 'components/Prompt'
import { required, integer } from 'lib/validators'
import { inferType } from './room-types'
import Stage from './types-edit/stage'
import PageStatic from './types-edit/page-static'
import PageIframe from './types-edit/page-iframe'
import ChannelVideo from './types-edit/channel-video'

const parseJSONConfig = function (value) {
	try {
		const config = JSON.parse(value)
		if (!config && typeof config !== 'object') {
			return {error: 'Must be an object'}
		}
		return {config}
	} catch (error) {
		return {error: error.message}
	}
}

export default {
	components: { Prompt },
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
				'channel-video': ChannelVideo
			},
			b_rawConfig: null,
			rawConfigError: null,
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
		},
		rawConfig: {
			get () {
				return this.b_rawConfig || JSON.stringify(this.config, null, 2)
			},
			set (value) {
				const {config, error} = parseJSONConfig(value)
				if (error) {
					this.b_rawConfig = value
					this.rawConfigError = error
				} else {
					this.b_rawConfig = null
					this.rawConfigError = null
					this.$emit('configChange', config)
				}
			}
		},
		errors () {
			const errorMessages = []
			const extractErrors = ($v) => {
				const params = Object.values($v.$params)
				for (const param of params) {
					if (param?.message) errorMessages.push(param.message)
				}
			}
			const traverse = ($v) => {
				if (!$v.$error) return
				const values = Object.entries($v).filter(([key]) => !key.startsWith('$'))
				extractErrors($v)
				for (const [, value] of values) {
					if (typeof value === 'object') traverse(value)
				}
			}

			traverse(this.$v)
			return errorMessages
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
	.bunt-tabs
		flex: auto
		tabs-style(active-color: var(--clr-primary), indicator-color: var(--clr-primary), background-color: transparent)
		flex: auto
		display: flex
		flex-direction: column
		min-height: 0
		margin: 0
		.bunt-tabs-header
			border-bottom: border-separator()
	.bunt-tabs-body
		flex: auto
		min-height: 0
		display: flex
		flex-direction: column
		.form-wrapper
			max-width: 640px
			padding: 16px
		.bunt-tab
			flex: auto
			display: flex
			flex-direction: column
			min-height: 0
	.raw-config
		.bunt-input-outline-container
			margin: 8px
			flex: auto
			textarea
				height: 100%
				background-color: transparent
				border: none
				outline: none
				resize: none
				min-height: 64px
				padding: 0 8px
		.raw-config-error
			color: $clr-danger
			font-weight: 600
			margin: 16px
	.form-actions
		flex: none
		display: flex
		align-items: center
		padding: 8px
		height: 56px
		box-sizing: border-box
		border-top: border-separator()
		background-color: $clr-grey-50
		.btn-save
			themed-button-primary()
		.errors
			color: $clr-danger
			font-weight: 600
			margin-left: 16px
</style>

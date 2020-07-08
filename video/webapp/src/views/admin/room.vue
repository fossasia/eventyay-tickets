<template lang="pug">
.c-admin-room(v-scrollbar.y="")
	.header
		h2 Room configuration
	bunt-progress-circular(size="huge", v-if="error == null && config == null")
	.error(v-if="error") We could not fetch the current configuration.
	.main-form(v-if="config != null")
		bunt-input(v-model="config.name", label="Name", name="name", :validation="$v.config.name")
		bunt-input(v-model="config.description", label="Description", name="description")
		bunt-input(v-model="config.sorting_priority", label="Sorting priority", name="sorting_priority", :validation="$v.config.sorting_priority")
		bunt-input(v-model="config.pretalx_id", label="pretalx ID", name="pretalx_id", :validation="$v.config.pretalx_id")
		upload-url-input(v-model="config.picture", label="Picture", name="picture")
		table.trait-grants
			thead
				tr
					th Role
					th Required traits
					th
			tbody
				tr(v-for="(val, key, index) in config.trait_grants")
					td
						bunt-input(:value="key", label="Role name", @input="set_role_name(key, $event)", name="n", :disabled="index < Object.keys(config.trait_grants).length - 1")
					td
						bunt-input(label="Required traits (comma-separated)", @input="set_trait_grants(key, $event)", name="g"
												:value="val ? val.join(', ') : ''")
					td.actions
						bunt-icon-button(@click="remove_role(key)") delete
			tfoot
				tr
					td
						bunt-button.btn-add-role(@click="add_role") Add role
					td
					td
		h3 Content
		div.modules
			div.module(v-for="(val, index) in config.module_config")
				h4 {{ val.type }}
					bunt-icon-button(@click="remove_module(val.type)") delete
				div(v-if="val.type == 'page.markdown'")
					bunt-input-outline-container(label="Content")
						textarea(slot-scope="{focus, blur}", @focus="focus", @blur="blur", v-model="val.config.content")
				div(v-else-if="val.type == 'page.iframe'")
					bunt-input(v-model="val.config.url", label="URL", name="url")
				div(v-else-if="val.type == 'livestream.native'")
					bunt-input(v-model="val.config.hls_url", label="HLS URL", name="url")
				div(v-else-if="val.type == 'call.bigbluebutton'")
					bunt-checkbox(v-model="val.config.record", label="Allow recording (needs to be set before first join)", name="record")
				div(v-else-if="val.type == 'chat.native'")
					bunt-checkbox(v-model="val.config.volatile", label="Users only join temporarily (use for large rooms, e.g. stage chats)", name="volatile")
			div.add-module
				bunt-select(v-model="add_module_type", label="Type", name="type", :options="unusedTypes")
				bunt-button.btn-add-module(@click="add_module") Add new module
		bunt-button.btn-save(@click="save", :loading="saving") Save
</template>
<script>
// TODO
// - search
import api from 'lib/api'
import i18n from '../../i18n'
import UploadUrlInput from '../../components/config/UploadUrlInput'
import { required, integer } from 'vuelidate/lib/validators'

const KNOWN_TYPES = [
	'page.markdown',
	'page.iframe',
	'livestream.native',
	'chat.native',
	'call.bigbluebutton'
]

export default {
	name: 'AdminRoom',
	components: { UploadUrlInput },
	props: {
		editRoomId: String
	},
	data () {
		return {
			config: null,
			add_module_type: null,

			saving: false,
			error: null
		}
	},
	computed: {
		locales () {
			return i18n.availableLocales
		},
		unusedTypes () {
			const usedTypes = this.config.module_config.map((m) => m.type)
			return KNOWN_TYPES.filter((t) => !usedTypes.includes(t))
		}
	},
	validations: {
		config: {
			name: {
				required
			},
			sorting_priority: {
				required,
				integer
			},
			pretalx_id: {
				integer
			},
		}
	},
	methods: {
		set_trait_grants (role, traits) {
			if (typeof this.config.trait_grants[role] !== 'undefined') {
				this.$set(this.config.trait_grants, role, traits.split(',').map((i) => i.trim()))
			}
		},
		remove_role (role) {
			this.$delete(this.config.trait_grants, role)
		},
		add_role () {
			this.$set(this.config.trait_grants, '', [])
		},
		toggle_trait_grants (role, toggle) {
			if (toggle) {
				this.$set(this.config.trait_grants, role, [])
			} else {
				this.$delete(this.config.trait_grants, role)
			}
		},
		set_role_name (old, n) {
			this.$set(this.config.trait_grants, n, this.config.trait_grants[old])
			this.$delete(this.config.trait_grants, old)
		},
		remove_module (type) {
			this.config.module_config = this.config.module_config.filter((m) => m.type !== type)
		},
		add_module () {
			if (this.add_module_type) {
				this.config.module_config.push({type: this.add_module_type, config: {}})
				this.add_module_type = null
			}
		},
		async save () {
			this.$v.$touch()
			if (this.$v.$invalid) return
			this.saving = true
			await api.call('room.config.patch', {
				room: this.editRoomId,
				name: this.config.name,
				description: this.config.description,
				sorting_priority: this.config.sorting_priority,
				pretalx_id: this.config.pretalx_id,
				picture: this.config.picture,
				trait_grants: this.config.trait_grants,
				module_config: this.config.module_config,
			})
			this.saving = false
			// TODO error handling
		},
	},
	async created () {
		// We don't use the global world object since it e.g. currently does not contain locale and timezone
		// TODO: Force reloading if world.updated is received from the server
		try {
			this.config = await api.call('room.config.get', {room: this.editRoomId})
		} catch (error) {
			this.error = error
			console.log(error)
		}
	}
}
</script>
<style lang="stylus">
.c-admin-room
	background white
	padding 16px
	.trait-grants
		width 100%
		th
			text-align left
			border-bottom 1px solid #ccc
			padding 10px
		td
			vertical-align center
		td.actions
			text-align right
	.module
		border 1px solid #cccccc
		border-radius 4px
		padding 5px 15px
		margin-bottom 15px
		.bunt-input-outline-container
			textarea
				background-color: transparent
				border: none
				outline: none
				resize: vertical
				min-height: 250px
				padding: 0 8px
	.add-module
		display flex
		flex-direction row
		align-items center
		margin 0 -15px
		.dropdown, button
			margin: 0 15px
			flex: 1
	h2
		margin-top 0
		margin-bottom 16px
	.btn-save
		margin-top 16px
		themed-button-primary(size: large)
	.btn-add-module
		themed-button-default()
	.btn-add-role
		margin 8px 0
		themed-button-default()
</style>

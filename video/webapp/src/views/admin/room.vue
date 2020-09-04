<template lang="pug">
.c-admin-room
	.error(v-if="error") We could not fetch the current configuration.
	template(v-else-if="config")
		.ui-page-header
			bunt-icon-button(@click="$router.push({name: 'admin:rooms'})") arrow_left
			h2 {{ config.name }} room configuration
			.actions
				bunt-button.btn-save(@click="save", :loading="saving") Save
		.main-form(v-scrollbar.y="")
			bunt-input(v-model="config.name", label="Name", name="name", :validation="$v.config.name")
			bunt-input(v-model="config.description", label="Description", name="description")
			bunt-input(v-model="config.sorting_priority", label="Sorting priority", name="sorting_priority", :validation="$v.config.sorting_priority")
			bunt-input(v-model="config.pretalx_id", label="pretalx ID", name="pretalx_id", :validation="$v.config.pretalx_id")
			bunt-checkbox(v-model="config.force_join", label="Force join on login (use for non-volatile, text-based chats only!!)", name="force_join")
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
							bunt-icon-button(@click="remove_role(key)") delete-outline
				tfoot
					tr
						td
							bunt-button.btn-add-role(@click="add_role") Add role
						td
						td
			h3 Content
			.modules
				.module(v-for="(val, index) in config.module_config")
					h4 {{ val.type }}
						bunt-icon-button(@click="remove_module(val.type)") delete-outline
					div(v-if="val.type == 'page.markdown'")
						bunt-input-outline-container(label="Content")
							textarea(slot-scope="{focus, blur}", @focus="focus", @blur="blur", v-model="val.config.content")
					div(v-else-if="val.type == 'page.landing'")
						bunt-input-outline-container(label="Content")
							textarea(slot-scope="{focus, blur}", @focus="focus", @blur="blur", v-model="val.config.content")
						upload-url-input(v-model="val.config.header_image", label="Header image", name="headerimage")
						bunt-input(v-model="val.config.header_background_color", label="Header background color", name="headerbackgroundcolor")
					div(v-else-if="val.type == 'page.iframe'")
						bunt-input(v-model="val.config.url", label="URL", name="url")
					div(v-else-if="val.type == 'livestream.native'")
						bunt-input(v-model="val.config.hls_url", label="HLS URL", name="url")
					div(v-else-if="val.type == 'call.bigbluebutton'")
						bunt-checkbox(v-model="val.config.record", label="Allow recording (needs to be set before first join)", name="record")
						bunt-checkbox(v-model="val.config.hide_presentation", label="Hide presentation when users join", name="hide_presentation")
						bunt-checkbox(v-model="val.config.waiting_room", label="Put new users in waiting room first (needs to be set before first join)", name="waiting_room")
						bunt-checkbox(v-model="val.config.auto_microphone", label="Auto-join users with microphone on (skip dialog asking how to join)", name="auto_microphone")
						bunt-input(v-model="val.config.voice_bridge", label="Voice Bridge ID", name="voice_bridge")
						bunt-input(v-model="val.config.prefer_server", label="Prefer Server with ID", name="prefer_server")
						upload-url-input(v-model="val.config.presentation", label="Initial presentation", name="presentation")
					div(v-else-if="val.type == 'chat.native'")
						bunt-checkbox(v-model="val.config.volatile", label="Users only join temporarily (use for large rooms, e.g. stage chats)", name="volatile")
				.add-module
					bunt-select(v-model="add_module_type", label="Type", name="type", :options="unusedTypes")
					bunt-button.btn-add-module(@click="add_module") Add new module
			.danger-zone
				h5 DANGER ZONE
				bunt-button.delete-room(icon="delete", @click="showDeletePrompt = true") delete
				span This action cannot be undone!
	bunt-progress-circular(v-else, size="huge")
	transition(name="prompt")
		prompt.delete-prompt(v-if="showDeletePrompt", @close="showDeletePrompt = false")
			.content
				.prompt-header
					h3 Are you ABSOLUTELY sure?
				p This action #[b CANNOT] be undone. This will permanently delete the room
				.room-name {{ config.name }}
				p Please type in the name of the Project to confirm.
				bunt-input(name="projectName", label="Room name", v-model="deletingRoomName")
				bunt-button.delete-room(icon="delete", :disabled="deletingRoomName !== config.name", @click="deleteRoom", :loading="deleting", :error-message="deleteError") delete this room
</template>
<script>
// TODO
// - search
import api from 'lib/api'
import Prompt from 'components/Prompt'
import UploadUrlInput from 'components/config/UploadUrlInput'
import { required, integer } from 'vuelidate/lib/validators'

const KNOWN_TYPES = [
	'page.markdown',
	'page.iframe',
	'page.landing',
	'livestream.native',
	'exhibition.native',
	'chat.native',
	'call.bigbluebutton'
]

export default {
	name: 'AdminRoom',
	components: { Prompt, UploadUrlInput },
	props: {
		editRoomId: String
	},
	data () {
		return {
			config: null,
			add_module_type: null,
			saving: false,
			error: null,
			showDeletePrompt: false,
			deletingRoomName: '',
			deleting: false,
			deleteError: null
		}
	},
	computed: {
		unusedTypes () {
			const usedTypes = this.config.module_config.map((m) => m.type)
			return KNOWN_TYPES.filter((t) => !usedTypes.includes(t))
		}
	},
	// TODO use message validators
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
	async created () {
		// We don't use the global world object since it e.g. currently does not contain locale and timezone
		// TODO: Force reloading if world.updated is received from the server
		try {
			this.config = await api.call('room.config.get', {room: this.editRoomId})
		} catch (error) {
			this.error = error
			console.log(error)
		}
	},
	methods: {
		set_trait_grants (role, traits) {
			if (typeof this.config.trait_grants[role] !== 'undefined') {
				this.$set(this.config.trait_grants, role, traits.split(',').map((i) => i.trim()).filter((i) => i.length > 0))
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
				force_join: this.config.force_join,
				module_config: this.config.module_config,
			})
			this.saving = false
			// TODO error handling
		},
		async deleteRoom () {
			this.deleting = true
			this.deleteError = null
			try {
				await api.call('room.delete', {room: this.config.id})
				this.$router.replace({name: 'admin:rooms'})
			} catch (error) {
				this.deleteError = this.$t(`error:${error.code}`)
			}
			this.deleting = false
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
	.bunt-icon-button
		icon-button-style(style: clear)
	.ui-page-header
		background-color: $clr-grey-100
		.bunt-icon-button
			margin-right: 8px
		h2
			flex: auto
			font-size: 21px
			font-weight: 500
			margin: 1px 16px 0 0
			ellipsis()

		.actions
			display: flex
			flex: none
			.bunt-button:not(:last-child)
				margin-right: 16px
			.btn-save
				themed-button-primary()
	.main-form
		display: flex
		flex-direction: column
		> *
			margin: 0 16px
	.trait-grants
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
	.btn-add-module
		themed-button-default()
	.btn-add-role
		margin 8px 0
		themed-button-default()

	.danger-zone
		margin: 50px 8px
		color: $clr-danger
		h5
			border-bottom: 2px solid $clr-danger
		.delete-room
			button-style(color: $clr-danger)
			margin: 0 8px

	.delete-prompt
		.content
			display: flex
			flex-direction: column
			padding: 16px
		.question-box-header
			margin-top: -10px
			margin-bottom: 15px
			align-items: center
			display: flex
			justify-content: space-between
		.room-name
			font-family: monospace
			font-size: 16px
			border: border-separator()
			border-radius: 4px
			padding: 4px 8px
			background-color: $clr-grey-100
			align-self: center
		.delete-room
			button-style(color: $clr-danger)
</style>

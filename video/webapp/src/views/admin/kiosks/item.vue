<template lang="pug">
.c-admin-kiosk
	.error(v-if="error") We could not fetch the current configuration.
	template(v-else-if="kiosk")
		.ui-page-header
			bunt-icon-button(@click="$router.push({name: 'admin:kiosks:index'})") arrow_left
			h1 {{ kiosk.profile.display_name }}
			.actions
				bunt-button.btn-delete-kiosk(@click="showDeletePrompt = true") delete
		.scroll-wrapper(v-scrollbar.y="")
			.ui-form-body
				.kiosk-url
					label Kiosk Login URL:
					.copyable-url(@click="copyLoginUrl")
						.url {{ loginUrl }}
						.mdi.mdi-content-copy
						.copy-success(v-if="urlCopied", v-tooltip="{text: 'Copied!', show: true, placement: 'top', fixed: true}")
				bunt-input(name="name", v-model="kiosk.profile.display_name", label="Name", :validation="$v.kiosk.profile.display_name")
				bunt-select(v-model="kiosk.profile.room_id", label="Room", name="room", :options="rooms", option-label="name", :validation="$v.kiosk.profile.room_id")
				color-picker(name="background_color", v-model="kiosk.profile.background_color", label="Background color", :validation="$v.kiosk.profile.background_color")
		.ui-form-actions
			bunt-button.btn-save(@click="save", :loading="saving", :error-message="saveError") Save
			.errors {{ validationErrors.join(', ') }}
	bunt-progress-circular(v-else, size="huge")
	transition(name="prompt")
		prompt.delete-prompt(v-if="showDeletePrompt", @close="showDeletePrompt = false")
			.content
				.prompt-header
					h3 Are you ABSOLUTELY sure?
				p This action #[b CANNOT] be undone. This will permanently delete the kiosk
				.kiosk-name {{ kiosk.profile.display_name }}
				p Please type in the name of the kiosk to confirm.
				bunt-input(name="deletingKioskName", label="Kiosk name", v-model="deletingKioskName", @keypress.enter="deleteKiosk")
				bunt-button.delete-kiosk(icon="delete", :disabled="deletingKioskName !== kiosk.profile.display_name", @click="deleteKiosk", :loading="deleting", :error-message="deleteError") delete this kiosk
</template>
<script>
import api from 'lib/api'
import { color, required } from 'lib/validators'
import { inferRoomType } from 'lib/room-types'
import ColorPicker from 'components/ColorPicker'
import Prompt from 'components/Prompt'
import ValidationErrorsMixin from 'components/mixins/validation-errors'

export default {
	name: 'AdminKiosk',
	components: { ColorPicker, Prompt },
	mixins: [ValidationErrorsMixin],
	props: {
		kioskId: String
	},
	data () {
		return {
			error: null,
			kiosk: null,
			saving: false,
			saveError: null,
			showDeletePrompt: false,
			deletingKioskName: '',
			deleting: false,
			deleteError: null,
			urlCopied: false
		}
	},
	computed: {
		rooms () {
			return this.$store.state.rooms.filter(room => inferRoomType(room)?.id === 'stage')
		},
		loginUrl () {
			return `${window.location.origin}/login/${this.kiosk.token}`
		}
	},
	validations: {
		kiosk: {
			profile: {
				display_name: {
					required: required('Name is required')
				},
				room_id: {
					required: required('Room is required')
				},
				background_color: {
					color: color('color must be in 3 or 6 digit hex format')
				},
			}
		}
	},
	async created () {
		try {
			this.kiosk = await api.call('user.kiosk.fetch', {id: this.kioskId})
		} catch (error) {
			this.error = error
			console.error(error)
		}
	},
	methods: {
		async save () {
			this.saveError = null
			this.$v.$touch()
			if (this.$v.$invalid) return
			this.saving = true
			try {
				await api.call('user.admin.update', {
					id: this.kiosk.id,
					profile: this.kiosk.profile
				})
			} catch (e) {
				this.saveError = e.message
			} finally {
				this.saving = false
			}
		},
		async deleteKiosk () {
			if (this.deletingKioskName !== this.kiosk.profile.display_name) return
			this.deleting = true
			this.deleteError = null
			try {
				await api.call('user.delete', {id: this.kiosk.id})
				this.$router.replace({name: 'admin:kiosks:index'})
			} catch (error) {
				this.deleteError = this.$t(`error:${error.code}`)
			}
			this.deleting = false
		},
		async copyLoginUrl () {
			await navigator.clipboard.writeText(this.loginUrl)
			this.urlCopied = true
			setTimeout(() => {
				this.urlCopied = false
			}, 3000)
		}
	}
}
</script>
<style lang="stylus">
.c-admin-kiosk
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
		.actions
			display: flex
			flex: none
			.bunt-button:not(:last-child)
				margin-right: 16px
			.btn-delete-kiosk
				button-style(color: $clr-danger)
	.scroll-wrapper
		flex: auto
		display: flex
		flex-direction: column

	.kiosk-url
		display: flex
		gap: 8px
		align-items: center
		.copyable-url
			position: relative
			display: flex
			gap: 8px
			padding: 4px
			background-color: $clr-grey-200
			border-radius: 2px
			cursor: pointer
			.copy-success
				position: absolute
				top: 0
				left: 0
				right: 0
				bottom: 0
				background-color: $clr-secondary-text-dark
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
		.kiosk-name
			font-family: monospace
			font-size: 16px
			border: border-separator()
			border-radius: 4px
			padding: 4px 8px
			background-color: $clr-grey-100
			align-self: center
		.delete-kiosk
			button-style(color: $clr-danger)
</style>

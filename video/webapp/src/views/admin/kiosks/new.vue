<template lang="pug">
.c-admin-kiosk-new
	.ui-page-header
		bunt-icon-button(@click="$router.replace({name: 'admin:kiosks:index'})") arrow_left
		h1 New kiosk
	.scroll-wrapper(v-scrollbar.y="")
		.ui-form-body
			bunt-input(name="name", v-model="profile.display_name", label="Name", :validation="$v.profile.display_name")
			bunt-select(v-model="profile.room_id", label="Room", name="room", :options="rooms", option-label="name", :validation="$v.profile.room_id")
	.ui-form-actions
		bunt-button.btn-save(@click="save", :loading="saving", :error-message="error") create
		.errors {{ validationErrors.join(', ') }}
</template>
<script>
import api from 'lib/api'
import { required } from 'lib/validators'
import { inferRoomType } from 'lib/room-types'
import ValidationErrorsMixin from 'components/mixins/validation-errors'

export default {
	components: {},
	mixins: [ValidationErrorsMixin],
	data () {
		return {
			profile: {
				display_name: ''
			},
			saving: false,
			error: null
		}
	},
	computed: {
		rooms () {
			return this.$store.state.rooms.filter(room => inferRoomType(room)?.id === 'stage')
		},
	},
	validations: {
		profile: {
			display_name: {
				required: required('Name is required')
			},
			room_id: {
				required: required('Room is required')
			}
		}
	},
	methods: {
		async save () {
			this.error = null
			this.$v.$touch()
			if (this.$v.$invalid) return
			this.saving = true
			try {
				const response = await api.call('user.kiosk.create', {
					profile: this.profile
				})
				this.$router.replace({name: 'admin:kiosks:item', params: {kioskId: response.user}})
			} catch (e) {
				this.error = e.message
			} finally {
				this.saving = false
			}
		}
	}
}
</script>
<style lang="stylus">
.c-admin-kiosk-new
	background-color: $clr-white
	display: flex
	flex-direction: column
	min-height: 0
	.scroll-wrapper
		flex: auto
		display: flex
		flex-direction: column
</style>

<template lang="pug">
.v-preferences(v-scrollbar.y="")
	h1 {{ $t('preferences/index:heading') }}
	.inputs
		.avatar-wrapper
			avatar(:user="{profile}", :size="128")
			bunt-button#btn-change-avatar(@click="showChangeAvatar = true") {{ $t('preferences/index:btn-change-avatar:label') }}
		bunt-input.display-name(name="displayName", :label="$t('profile/GreetingPrompt:displayname:label')", v-model.trim="profile.display_name", :validation="$v.profile.display_name")
		change-additional-fields(v-model="profile.fields")
		bunt-button#btn-save(:disabled="$v.$invalid && $v.$dirty", :loading="saving", @click="save") {{ $t('preferences/index:btn-save:label') }}
	transition(name="prompt")
		prompt.change-avatar-prompt(v-if="showChangeAvatar", @close="showChangeAvatar = false")
			.content
				change-avatar(ref="avatar", v-model="profile.avatar")
				.actions
					bunt-button#btn-cancel(@click="showChangeAvatar = false") {{ $t('Prompt:cancel:label') }}
					bunt-button#btn-upload(:loading="savingAvatar", @click="uploadAvatar") {{ $t('preferences/index:btn-upload-save:label') }}
</template>
<script>
import { mapState } from 'vuex'
import Avatar from 'components/Avatar'
import Prompt from 'components/Prompt'
import ChangeAvatar from 'components/profile/ChangeAvatar'
import ChangeAdditionalFields from 'components/profile/ChangeAdditionalFields'
import ConnectGravatar from 'components/profile/ConnectGravatar'
import { required } from 'buntpapier/src/vuelidate/validators'

export default {
	components: { Avatar, Prompt, ChangeAvatar, ChangeAdditionalFields, ConnectGravatar},
	data () {
		return {
			profile: null,
			showChangeAvatar: false,
			savingAvatar: false,
			saving: false
		}
	},
	validations: {
		profile: {
			display_name: {
				required: required('Display name cannot be empty')
			}
		}
	},
	computed: {
		...mapState(['user', 'world']),
	},
	created () {
		this.profile = Object.assign({}, this.user.profile)
		if (!this.profile.avatar || (!this.profile.avatar.url && !this.profile.avatar.identicon)) {
			this.profile.avatar = {
				identicon: this.user.id
			}
		}
	},
	methods: {
		async uploadAvatar () {
			this.savingAvatar = true
			await this.$refs.avatar.update()
			await this.$store.dispatch('updateUser', {profile: Object.assign({}, this.user.profile, {avatar: this.profile.avatar})})
			this.showChangeAvatar = false
			this.savingAvatar = false
		},
		async save () {
			this.$v.$touch()
			if (this.$v.$invalid) return
			this.saving = true
			await this.$store.dispatch('updateUser', {profile: this.profile})
			this.saving = false
		}
	}
}
</script>
<style lang="stylus">
.v-preferences
	background-color: $clr-white
	display: flex
	flex-direction: column
	padding: 16px 32px
	h1
		margin: 0
	.avatar-wrapper
		display: flex
		align-items: center
		#btn-change-avatar
			themed-button-secondary()
			margin-left: 16px
	.inputs
		width: 320px
	#btn-save
		themed-button-primary()

	.change-avatar-prompt
		.content
			display: flex
			flex-direction: column
			padding: 48px 32px 32px
		.actions
			margin-top: 32px
			align-self: stretch
			display: flex
			justify-content: flex-end
		#btn-cancel
			themed-button-secondary()
			margin-right: 8px
		#btn-upload
			themed-button-primary()
</style>

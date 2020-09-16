<template lang="pug">
.c-admin-user
	template(v-if="user")
		.ui-page-header
			bunt-icon-button(@click="$router.push({name: 'admin:users'})") arrow_left
			h2 User: {{ (user.profile && user.profile.display_name) || user.id }}
			.actions(v-if="user.id !== ownUser.id")
				bunt-button.btn-dm(@click="openDM") message
				bunt-button.btn-call( @click="startCall") call
				bunt-button.btn-reactivate(v-if="user.moderation_state", @click="userAction = 'reactivate'")
					| {{ user.moderation_state === 'banned' ? 'unban' : 'unsilence'}}
				bunt-button.btn-ban(v-if="user.moderation_state !== 'banned'", @click="userAction = 'ban'") ban
				bunt-button.btn-silence(v-if="!user.moderation_state", @click="userAction = 'silence'") silence
				bunt-button#btn-save(v-if="edit", :disabled="$v.$invalid && $v.$dirty", :loading="saving", @click="save") {{ $t('preferences/index:btn-save:label') }}
				bunt-button#btn-edit(v-else, @click="edit=true") edit
		.user-info(v-scrollbar.y="")
			.avatar-wrapper
				avatar(:user="user", :size="128")
				bunt-button#btn-change-avatar(@click="showChangeAvatar = true", v-if="edit") {{ $t('preferences/index:btn-change-avatar:label') }}
			bunt-input.display-name(name="displayName", :label="$t('profile/GreetingPrompt:displayname:label')", v-model.trim="user.profile.display_name", :validation="$v.user.profile.display_name", :disabled="!edit")
			bunt-input(name="id", label="ID", :value="user.id", :disabled="true")
			bunt-input(name="mod_state", label="Moderation state", :value="user.moderation_state || '-'", :disabled="true")
			change-additional-fields(v-model="user.profile.fields", :disabled="!edit")
	bunt-progress-circular(v-else, size="huge")
	transition(name="prompt")
		user-action-prompt(v-if="userAction", :action="userAction", :user="user", :closeDelay="0", @close="completedUserAction")
	transition(name="prompt")
		prompt.change-avatar-prompt(v-if="showChangeAvatar", @close="showChangeAvatar = false")
			.content
				change-avatar(ref="avatar", v-model="user.profile.avatar", @blockSave="blockSave = $event")
				.actions
					bunt-button#btn-cancel(@click="showChangeAvatar = false") {{ $t('Prompt:cancel:label') }}
					bunt-button#btn-upload(:loading="savingAvatar", :disabled="blockSave", @click="uploadAvatar") {{ $t('preferences/index:btn-upload-save:label') }}
</template>
<script>
import { mapState } from 'vuex'
import api from 'lib/api'
import Avatar from 'components/Avatar'
import Prompt from 'components/Prompt'
import ChangeAvatar from 'components/profile/ChangeAvatar'
import UserActionPrompt from 'components/UserActionPrompt'
import ChangeAdditionalFields from 'components/profile/ChangeAdditionalFields'
import { required } from 'buntpapier/src/vuelidate/validators'

export default {
	components: { Avatar, Prompt, UserActionPrompt, ChangeAdditionalFields, ChangeAvatar },
	props: {
		userId: String
	},
	data () {
		return {
			user: null,
			userAction: null,
			showChangeAvatar: false,
			savingAvatar: false,
			blockSave: false,
			saving: false,
			edit: false
		}
	},
	validations: {
		user: {
			profile: {
				display_name: {
					required: required('Display name cannot be empty')
				}
			}
		}
	},
	computed: {
		...mapState({
			ownUser: 'user'
		}),
	},
	async created () {
		this.user = await api.call('user.fetch', {id: this.userId})
	},
	methods: {
		async openDM () {
			// TODO loading indicator
			await this.$store.dispatch('chat/openDirectMessage', {users: [this.user]})
		},
		async startCall () {
			const channel = await this.$store.dispatch('chat/openDirectMessage', {users: [this.user]})
			await this.$store.dispatch('chat/startCall', {channel})
		},
		async completedUserAction () {
			this.userAction = null
			this.user = await api.call('user.fetch', {id: this.userId})
		},
		async uploadAvatar () {
			this.savingAvatar = true
			await this.$refs.avatar.update()
			await this.$store.dispatch('adminUpdateUser', {profile: Object.assign({}, this.user.profile, {avatar: this.user.profile.avatar}), id: this.user.id})
			this.showChangeAvatar = false
			this.savingAvatar = false
			this.edit = false
		},
		async save () {
			this.$v.$touch()
			if (this.$v.$invalid) return
			this.saving = true
			await this.$store.dispatch('adminUpdateUser', {profile: this.user.profile, id: this.user.id})
			this.saving = false
			this.edit = false
		}
	}
}
</script>
<style lang="stylus">
.c-admin-user
	background-color $clr-white
	display flex
	flex-direction column
	min-height 0
	.bunt-icon-button
		icon-button-style(style: clear)
	.ui-page-header
		background-color $clr-grey-100
		.bunt-icon-button
			margin-right 8px
		h2
			flex auto
			font-size 21px
			font-weight 500
			margin 1px 16px 0 0
			ellipsis()
		.actions
			display flex
			flex none
			.bunt-button:not(:last-child)
				margin-right 16px
			.btn-dm, .btn-call
				button-style(style: clear)
			.btn-reactivate
				button-style(color: $clr-success)
			.btn-ban
				button-style(color: $clr-danger)
			.btn-silence
				button-style(color: $clr-deep-orange)
			#btn-save
				themed-button-primary()
			#btn-edit
				button-style(color: $clr-danger)
	.user-info
		display flex
		flex-direction column
		padding 32px
		.avatar-wrapper
			display flex
			align-items center
			#btn-change-avatar
				themed-button-secondary()
				margin-left 16px

	.change-avatar-prompt
		.content
			display flex
			flex-direction column
			padding 48px 32px 32px
		.actions
			margin-top 32px
			align-self stretch
			display flex
			justify-content flex-end
		#btn-cancel
			themed-button-secondary()
			margin-right 8px
		#btn-upload
			themed-button-primary()

</style>

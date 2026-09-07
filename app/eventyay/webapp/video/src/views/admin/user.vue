<template lang="pug">
.c-admin-user
	template(v-if="user")
		.ui-page-header
			bunt-icon-button(@click="$router.push({name: 'admin:users'})", :tooltip="$t('Back to Users')", tooltip-placement="bottom-start", :tooltip-fixed="true") arrow-left
			h1 {{ $t('User') }} {{ (user.profile && user.profile.display_name) || user.id }}
			.actions(v-if="user.id !== ownUser.id")
				bunt-button.btn-dm(v-if="hasPermission('world:chat.direct') && liveFeatures.direct_messaging && !user.deleted", @click="openDM") {{ $t('message') }}
				bunt-button.btn-call(v-if="hasPermission('world:chat.direct') && liveFeatures.direct_messaging && !user.deleted", @click="startCall") {{ $t('call') }}
				bunt-button.btn-delete(v-if="hasPermission('world:users.manage') && !user.deleted", @click="userAction = 'delete'") {{ $t('delete') }}
				bunt-button.btn-ban(v-if="hasPermission('world:users.manage') && !user.deleted && user.moderation_state !== 'banned'", @click="userAction = 'ban'") {{ $t('ban') }}
				bunt-button.btn-silence(v-if="hasPermission('world:users.manage') && !user.deleted && !user.moderation_state", @click="userAction = 'silence'") {{ $t('silence') }}
				bunt-button.btn-reactivate(v-if="hasPermission('world:users.manage') && user.moderation_state", @click="userAction = 'reactivate'")
					| {{ user.moderation_state === 'banned' ? $t('unban') : $t('unsilence') }}
				bunt-button#btn-save(v-if="edit", :disabled="v$.$invalid && v$.$dirty", :loading="saving", @click="save") {{ $t('save') }}
				bunt-button#btn-edit(v-if="!user.deleted", @click="edit=true") {{ $t('edit') }}
		scrollbars.user-info(y)
			.avatar-wrapper
				avatar(:user="user", :size="128")
				bunt-button#btn-change-avatar(@click="showChangeAvatar = true", v-if="edit") {{ $t('change avatar') }}
			bunt-input.display-name(name="displayName", :label="$t('Display name')", v-model.trim="user.profile.display_name", :validation="v$.user.profile.display_name", :disabled="!edit")
			bunt-input(name="id", :label="$t('ID')", :modelValue="user.id", :disabled="true")
			bunt-input(name="token_id", :label="$t('Login UID (JWT uid)')", :modelValue="user.token_id || '–'", :disabled="true")
			bunt-input(name="email", :label="$t('Email')", :modelValue="user.email || '–'", :disabled="true")
			bunt-input(name="wikimedia_username", :label="$t('Wikimedia / Wikimania username')", :modelValue="user.wikimedia_username || '–'", :disabled="true")
			bunt-input(name="order_code", :label="$t('Order code')", :modelValue="user.order_code || '–'", :disabled="true")
			bunt-input(name="ticket_code", :label="$t('Ticket code (position secret)')", :modelValue="user.ticket_code || '–'", :disabled="true")
			bunt-input(name="mod_state", :label="$t('Moderation state')", :modelValue="user.moderation_state || '-'", :disabled="true")
	bunt-progress-circular(v-else, size="huge")
	transition(name="prompt")
		user-action-prompt(v-if="userAction", :action="userAction", :user="user", :closeDelay="0", @close="completedUserAction")
	transition(name="prompt")
		prompt.change-avatar-prompt(v-if="showChangeAvatar", @close="showChangeAvatar = false")
			.content
				change-avatar(ref="avatar", v-model="user.profile.avatar", :profile="user.profile", @blockSave="blockSave = $event")
				.actions
					bunt-button#btn-cancel(@click="showChangeAvatar = false") {{ $t('cancel') }}
					bunt-button#btn-upload(:loading="savingAvatar", :disabled="blockSave", @click="uploadAvatar") {{ $t('save') }}
</template>
<script>
import { useVuelidate } from '@vuelidate/core'
import { mapState, mapGetters } from 'vuex'
import api from 'lib/api'
import Avatar from 'components/Avatar'
import Prompt from 'components/Prompt'
import ChangeAvatar from 'components/profile/ChangeAvatar'
import UserActionPrompt from 'components/UserActionPrompt'
import { required } from 'lib/validators'

export default {
	components: { Avatar, Prompt, UserActionPrompt, ChangeAvatar },
	props: {
		userId: String
	},
	setup:() => ({v$:useVuelidate()}),
	data() {
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
	validations() {
		return {
			user: {
				profile: {
					display_name: {
						required: required(this.$t('Display name cannot be empty'))
					}
				}
			}
		}
	},
	computed: {
		...mapState({
			ownUser: 'user',
			world: 'world'
		}),
		...mapGetters(['hasPermission']),
		liveFeatures() {
			return Object.assign({
				chat_rooms: false,
				kiosks: false,
				direct_messaging: false,
				announcements: true
			}, this.world?.live_features || window.eventyay?.liveFeatures || {})
		},
	},
	async created() {
		this.user = await api.call('user.fetch', {id: this.userId})
	},
	methods: {
		async openDM() {
			// TODO loading indicator
			await this.$store.dispatch('chat/openDirectMessage', {users: [this.user]})
		},
		async startCall() {
			const channel = await this.$store.dispatch('chat/openDirectMessage', {users: [this.user]})
			await this.$store.dispatch('chat/startCall', {channel})
		},
		async completedUserAction() {
			this.userAction = null
			this.user = await api.call('user.fetch', {id: this.userId})
		},
		async uploadAvatar() {
			this.savingAvatar = true
			await this.$refs.avatar.update()
			await this.$store.dispatch('adminUpdateUser', {profile: Object.assign({}, this.user.profile, {avatar: this.user.profile.avatar}), id: this.user.id})
			this.showChangeAvatar = false
			this.savingAvatar = false
			this.edit = false
		},
		async save() {
			this.v$.$touch()
			if (this.v$.$invalid) return
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
	background-color: $clr-white
	display: flex
	flex-direction: column
	min-height: 0
	min-width: 0
	.bunt-icon-button
		icon-button-style(style: clear)
	.ui-page-header
		background-color: $clr-grey-100
		.bunt-icon-button
			margin-right: 8px
		.actions
			display: flex
			flex: none
			.bunt-button:not(:last-child)
				margin-right: 16px
			.btn-dm, .btn-call
				button-style(style: clear)
			.btn-reactivate
				button-style(color: $clr-success)
			.btn-ban, .btn-delete
				button-style(color: $clr-danger)
			.btn-silence
				button-style(color: $clr-deep-orange)
			#btn-save
				themed-button-primary()
			#btn-edit
				button-style(color: $clr-danger)
	.user-info
		display: flex
		flex-direction: column
		padding: 32px
		.avatar-wrapper
			display: flex
			align-items: center
			#btn-change-avatar
				themed-button-secondary()
				margin-left: 16px

	.change-avatar-prompt
		.content
			display: flex
			flex-direction: column
			padding: 48px 32px 32px
			min-height: 0
		.actions
			margin-top: 32px
			align-self: stretch
			display: flex
			justify-content: flex-end
			flex-shrink: 0
		#btn-cancel
			themed-button-secondary()
			margin-right: 8px
		#btn-upload
			themed-button-primary()

</style>

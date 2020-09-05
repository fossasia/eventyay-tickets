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
		table.user-info
			tr
				th Avatar:
				td: avatar(:user="user", :size="128")
			tr
				th ID:
				td {{ user.id }}
			tr(v-if="user.profile")
				th Display name:
				td {{ user.profile.display_name }}
			tr
				th Moderation state:
				td {{ user.moderation_state }}
			template(v-if="user.profile.fields")
				tr(v-for="(value, key) of user.profile.fields")
					th {{ key }}:
					td {{ value }}
	bunt-progress-circular(v-else, size="huge")
	transition(name="prompt")
		user-action-prompt(v-if="userAction", :action="userAction", :user="user", :closeDelay="0", @close="completedUserAction")
</template>
<script>
import { mapState } from 'vuex'
import api from 'lib/api'
import Avatar from 'components/Avatar'
import UserActionPrompt from 'components/UserActionPrompt'

export default {
	components: { Avatar, UserActionPrompt },
	props: {
		userId: String
	},
	data () {
		return {
			user: null,
			userAction: null
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
		}
	}
}
</script>
<style lang="stylus">
.c-admin-user
	background-color: $clr-white
	display: flex
	flex-direction: column
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
			.btn-dm, .btn-call
				button-style(style: clear)
			.btn-reactivate
				button-style(color: $clr-success)
			.btn-ban
				button-style(color: $clr-danger)
			.btn-silence
				button-style(color: $clr-deep-orange)
	.user-info
		margin: 32px
		align-self: flex-start
		th
			padding: 4px
			text-align: right
</style>

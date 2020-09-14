<template lang="pug">
.c-userlist
	.profile
		bunt-progress-circular(size="huge", v-if="loading")
		template(v-else-if="selectedUser")
			avatar(:user="selectedUser", :size="128")
			h1.display-name
				| {{ selectedUser.profile ? selectedUser.profile.display_name : (selectedUser.id ? selectedUser.id : '(unknown user)') }}
				.ui-badge(v-for="badge in selectedUser.badges") {{ badge }}
			.state {{ userStates.join(', ') }}
			.fields(v-if="availableFields")
				.field(v-for="field of availableFields")
					.label {{ field.label }}
					.value {{ field.value }}
			.actions(v-if="selectedUser.id !== user.id && selectedUser.id")
				.action-row
					bunt-button.btn-dm(v-if="hasPermission('world:chat.direct')", @click="openDM") message
					bunt-button.btn-call(v-if="hasPermission('world:chat.direct')", @click="startCall") call
					bunt-button.unblock(v-if="isBlocked", @click="userAction = 'unblock'") unblock
					bunt-button.block(v-else, @click="userAction = 'block'") block
				template(v-if="$features.enabled('chat-moderation') && hasPermission('room:chat.moderate') && selectedUser.id !== user.id")
					.devider Moderator Actions
					.action-row
						bunt-button.reactivate(v-if="selectedUser.moderation_state", @click="userAction = 'reactivate'")
							| {{ selectedUser.moderation_state === 'banned' ? 'unban' : 'unsilence'}}
						bunt-button.ban(v-if="selectedUser.moderation_state !== 'banned'", @click="userAction = 'ban'") ban
						bunt-button.silence(v-if="!selectedUser.moderation_state", @click="userAction = 'silence'") silence
	UserSearch(placeholder="Search", @selected="selectUser").user-list
	user-action-prompt(v-if="userAction", :action="userAction", :user="selectedUser", @close="updateProfile")
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import api from 'lib/api'
import Avatar from 'components/Avatar'
import UserSearch from 'components/UserSearch'
import UserActionPrompt from 'components/UserActionPrompt'

export default {
	components: { Avatar, UserSearch, UserActionPrompt },
	props: {
		room: Object,
		module: {
			type: Object,
			required: true
		}
	},
	data () {
		return {
			loading: false,
			blockedUsers: null,
			selectedUser: null,
			userAction: null,
			moderationError: null
		}
	},
	computed: {
		...mapState(['user', 'world']),
		...mapGetters(['hasPermission']),
		isBlocked () {
			if (!this.blockedUsers) return
			return this.blockedUsers.some(user => user.id === this.selectedUser.id)
		},
		availableFields () {
			if (!this.selectedUser.profile?.fields) return
			return this.world?.profile_fields
				.map(field => ({label: field.label, value: this.selectedUser.profile.fields[field.id]}))
				.filter(field => !!field.value)
		},
		userStates () {
			const states = []
			if (this.isBlocked) {
				states.push('blocked')
			}
			if (this.selectedUser.moderation_state) {
				states.push(this.selectedUser.moderation_state)
			}
			return states
		}
	},
	async created () {
		this.blockedUsers = (await api.call('user.list.blocked')).users
	},
	methods: {
		async updateProfile () {
			this.loading = true
			this.userAction = null
			this.blockedUsers = (await api.call('user.list.blocked')).users
			this.selectedUser = await api.call('user.fetch', {id: this.selectedUser.id})
			this.loading = false
		},
		selectUser: function (user) {
			this.selectedUser = user
		},
		async openDM () {
			await this.$store.dispatch('chat/openDirectMessage', {users: [this.selectedUser]})
		},
		async startCall () {
			const channel = await this.$store.dispatch('chat/openDirectMessage', {users: [this.selectedUser]})
			await this.$store.dispatch('chat/startCall', {channel})
		}
	}
}
</script>
<style lang="stylus">
.c-userlist
	flex auto
	background-color $clr-white
	display flex
	.user-list
		flex none
		display flex
		flex-direction column
		width 240px
		grid-area sidebar
		border-left border-separator()
		min-height 0
		height 100%
	.profile
		flex auto
		display flex
		flex-direction column
		min-width 0
		padding: 16px 32px
		h1
			margin: 0
			.display-name
				margin auto 8px
				flex auto
				ellipsis()
		.fields
			display flex
			flex-direction column
			align-self stretch
			margin 0 8px
			.field
				display flex
				flex-direction column
				margin 4px
				.label
					color $clr-secondary-text-light
					font-weight 500
					font-size 12px
				.value
					margin 2px 0 0 8px
		.state
			height 16px
			margin-bottom 8px
		.actions
			margin-top auto
		.action-row
			margin 8px 0px 8px 0px
			display flex
			align-self stretch
			justify-content flex-start
			.bunt-button
				button-style(style: clear)
			.bunt-icon-button
				icon-button-style(style: clear)
		.devider
			color $clr-secondary-text-light
			font-weight 500
			font-size 12px
			margin 0px 8px

</style>

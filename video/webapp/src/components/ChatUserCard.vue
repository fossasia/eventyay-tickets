<template lang="pug">
.c-chat-user-card
	.ui-background-blocker(v-if="!userAction", @click="$emit('close')")
	.user-card(v-if="!userAction", ref="card", @mousedown="showMoreActions=false")
		avatar(:user="sender", :size="128")
		.name
			| {{ sender.profile ? sender.profile.display_name : (sender.id ? sender.id : '(unknown user)') }}
			.ui-badge(v-for="badge in sender.badges") {{ badge }}
		.fields(v-if="availableFields")
			.field(v-for="field of availableFields")
				.label {{ field.label }}
				.value {{ field.value }}
		.state {{ userStates.join(', ') }}
		.actions(v-if="sender.id !== user.id && sender.id")
			bunt-button.btn-dm(v-if="hasPermission('world:chat.direct')", @click="openDM") message
			bunt-button.btn-call(v-if="hasPermission('world:chat.direct')", @click="startCall") call
			menu-dropdown(v-if="$features.enabled('chat-moderation') && (hasPermission('room:chat.moderate') || sender === user.id)", v-model="showMoreActions", :blockBackground="false", @mousedown.native.stop="")
				template(v-slot:button="{toggle}")
					bunt-icon-button(@click="toggle") dots-vertical
				template(v-slot:menu)
					.unblock(v-if="isBlocked", @click="userAction = 'unblock'") unblock
					.block(v-else, @click="userAction = 'block'") block
					template(v-if="$features.enabled('chat-moderation') && hasPermission('room:chat.moderate') && sender.id !== user.id")
						.divider Moderator Actions
						.reactivate(v-if="sender.moderation_state", @click="userAction = 'reactivate'")
							| {{ sender.moderation_state === 'banned' ? 'unban' : 'unsilence'}}
						.ban(v-if="sender.moderation_state !== 'banned'", @click="userAction = 'ban'") ban
						.silence(v-if="!sender.moderation_state", @click="userAction = 'silence'") silence
	user-action-prompt(v-if="userAction", :action="userAction", :user="sender", @close="$emit('close')")
</template>
<script>
// TODO
// - i18n
import { mapState, mapGetters } from 'vuex'
import api from 'lib/api'
import Avatar from 'components/Avatar'
import MenuDropdown from 'components/MenuDropdown'
import UserActionPrompt from 'components/UserActionPrompt'
export default {
	components: { Avatar, MenuDropdown, UserActionPrompt },
	props: {
		sender: Object,
	},
	data () {
		return {
			blockedUsers: null,
			showMoreActions: false,
			userAction: null,
			moderationError: null
		}
	},
	computed: {
		...mapState(['user', 'world']),
		...mapGetters(['hasPermission']),
		isBlocked () {
			if (!this.blockedUsers) return
			return this.blockedUsers.some(user => user.id === this.sender.id)
		},
		availableFields () {
			if (!this.sender.profile?.fields) return
			return this.world?.profile_fields
				.map(field => ({label: field.label, value: this.sender.profile.fields[field.label]}))
				.filter(field => !!field.value)
		},
		userStates () {
			const states = []
			if (this.isBlocked) {
				states.push('blocked')
			}
			if (this.sender.moderation_state) {
				states.push(this.sender.moderation_state)
			}
			return states
		}
	},
	async created () {
		this.blockedUsers = (await api.call('user.list.blocked')).users
	},
	methods: {
		async openDM () {
			// TODO loading indicator
			await this.$store.dispatch('chat/openDirectMessage', {users: [this.sender]})
		},
		async startCall () {
			const channel = await this.$store.dispatch('chat/openDirectMessage', {users: [this.sender]})
			await this.$store.dispatch('chat/startCall', {channel})
		}
	}
}
</script>
<style lang="stylus">
.c-chat-user-card
	.user-card
		card()
		z-index: 801
		display: flex
		flex-direction: column
		align-items: center
		padding: 8px
		min-width: 196px
		.name
			font-size: 24px
			font-weight: 600
			margin-top: 8px
		.fields
			display: flex
			flex-direction: column
			align-self: stretch
			margin: 0 8px
			.field
				display: flex
				flex-direction: column
				margin: 4px
				.label
					color: $clr-secondary-text-light
					font-weight: 500
					font-size: 12px
				.value
					margin: 2px 0 0 8px
		.state
			height: 16px
		.actions
			margin-top: 16px
			display: flex
			.bunt-button
				button-style(style: clear)
			.bunt-icon-button
				icon-button-style(style: clear)
			.c-menu-dropdown .menu
				.delete-message
					color: $clr-danger
					&:hover
						background-color: $clr-danger
						color: $clr-primary-text-dark
				.reactivate, .unblock
					color: $clr-success
					&:hover
						background-color: $clr-success
						color: $clr-primary-text-dark
				.ban, .block
					color: $clr-danger
					&:hover
						background-color: $clr-danger
						color: $clr-primary-text-dark
				.silence
					color: $clr-deep-orange
					&:hover
						background-color: $clr-deep-orange
						color: $clr-primary-text-dark
</style>

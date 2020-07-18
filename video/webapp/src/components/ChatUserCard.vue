<template lang="pug">
.c-chat-user-card
	.g-background-blocker(v-if="!userAction", @click="$emit('close')")
	.user-card(v-if="!userAction", ref="card", @mousedown="showMoreActions=false")
		avatar(:user="sender", :size="128")
		.name {{ sender.profile ? sender.profile.display_name : this.message.sender }}
		.state {{ userStates.join(', ') }}
		.actions(v-if="sender.id !== user.id")
			bunt-button.btn-dm(v-if="hasPermission('world:chat.direct')", @click="openDM") message
			bunt-button.btn-call(v-if="hasPermission('world:chat.direct')", @click="startCall") call
			menu-dropdown(v-if="$features.enabled('chat-moderation') && (hasPermission('room:chat.moderate') || message.sender === user.id)", v-model="showMoreActions", :blockBackground="false", @mousedown.native.stop="")
				template(v-slot:button="{toggle}")
					bunt-icon-button(@click="toggle") dots-vertical
				template(v-slot:menu)
					.block(@click="userAction = 'block'") block
					template(v-if="$features.enabled('chat-moderation') && hasPermission('room:chat.moderate') && sender.id !== user.id")
						.divider Moderator Actions
						.reactivate(v-if="sender.moderation_state", @click="userAction = 'reactivate'")
							| {{ sender.moderation_state === 'banned' ? 'unban' : 'unsilence'}}
						.ban(v-if="sender.moderation_state !== 'banned'", @click="userAction = 'ban'") ban
						.silence(v-if="!sender.moderation_state", @click="userAction = 'silence'") silence
	user-action-prompt(v-if="userAction", :action="userAction", :user="sender", @close="$emit('close')")
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import Avatar from 'components/Avatar'
import MenuDropdown from 'components/MenuDropdown'
import UserActionPrompt from 'components/UserActionPrompt'
export default {
	props: {
		sender: Object,
	},
	components: { Avatar, MenuDropdown, UserActionPrompt },
	data () {
		return {
			showMoreActions: false,
			userAction: null,
			moderationError: null
		}
	},
	computed: {
		...mapState(['user']),
		...mapGetters(['hasPermission']),
		userStates () {
			const states = []
			states.push(this.sender.moderation_state)
			// TODO blocked
			return states
		}
	},
	created () {},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {
		async openDM () {
			// TODO loading indicator
			await this.$store.dispatch('chat/openDirectMessage', {user: this.sender})
		},
		async startCall () {
			const channel = await this.$store.dispatch('chat/openDirectMessage', {user: this.sender})
			await this.$store.dispatch('chat/startCall', {channel})
		},
		async blockUser () {
			this.$store.dispatch('chat/blockUser', {user: this.sender})
			this.$emit('close')
		}
	}
}
</script>
<style lang="stylus">
.c-chat-user-card
	.user-card
		card()
		z-index: 5000
		display: flex
		flex-direction: column
		padding: 8px
		.name
			font-size: 24px
			font-weight: 600
			margin-top: 8px
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
				.reactivate
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

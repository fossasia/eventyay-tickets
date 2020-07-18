<template lang="pug">
.c-chat-user-card
	.g-background-blocker(@click="$emit('close')")
	.user-card(ref="card", @mousedown="showMoreActions=false")
		avatar(:user="sender", :size="128")
		.name {{ sender.profile ? sender.profile.display_name : this.message.sender }}
		.state {{ userStates.join(', ') }}
		.actions(v-if="sender.id !== user.id")
			bunt-button.btn-dm(v-if="hasPermission('world:chat.direct')", @click="openDM") message
			bunt-button.btn-call(v-if="hasPermission('world:chat.direct')", @click="openDM") call
			menu-dropdown(v-if="$features.enabled('chat-moderation') && (hasPermission('room:chat.moderate') || message.sender === user.id)", v-model="showMoreActions", :blockBackground="false", @mousedown.native.stop="")
				template(v-slot:button="{toggle}")
					bunt-icon-button(@click="toggle") dots-vertical
				template(v-slot:menu)
					.block(@click="openDM") block
					template(v-if="$features.enabled('chat-moderation') && hasPermission('room:chat.moderate') && sender.id !== user.id")
						.divider Moderator Actions
						.reactivate(
							v-if="sender.moderation_state",
							:loading="moderating === 'reactivate'",
							:error-message="(moderationError && moderationError.action === 'reactivate') ? moderationError.message : null",
							@click="moderateAction('reactivate')", :key="`${sender.id}-reactivate`")
							| {{ sender.moderation_state === 'banned' ? 'unban' : 'unsilence'}}
						.ban(
							v-if="sender.moderation_state !== 'banned'",
							:loading="moderating === 'ban'",
							:error-message="(moderationError && moderationError.action === 'ban') ? moderationError.message : null",
							@click="moderateAction('ban')", :key="`${sender.id}-ban`")
							| ban
						.silence(
							v-if="!sender.moderation_state",
							:loading="moderating === 'silence'",
							:error-message="(moderationError && moderationError.action === 'silence') ? moderationError.message : null",
							@click="moderateAction('silence')", :key="`${sender.id}-silence`")
							| silence
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import Avatar from 'components/Avatar'
import MenuDropdown from 'components/MenuDropdown'

export default {
	props: {
		sender: Object,
	},
	components: { Avatar, MenuDropdown },
	data () {
		return {
			showMoreActions: false,
			moderating: false,
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
			const channel = await this.$store.dispatch('chat/openDirectMessage', {user: this.sender})
			this.$router.push({name: 'channel', params: {channelId: channel.id}})
		},
		async moderateAction (action) {
			this.moderating = action
			this.moderationError = null
			try {
				await this.$store.dispatch('chat/moderateUser', {action, user: this.sender})
			} catch (error) {
				this.moderationError = {
					action,
					message: this.$t(`error:${error.code}`)
				}
			}
			this.moderating = null
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

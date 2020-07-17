<template lang="pug">
.c-chat-user-card
	avatar(:user="sender", :size="128")
	.name {{ sender.profile ? sender.profile.display_name : this.message.sender }}
	bunt-button.btn-dm(v-if="hasPermission('world:chat.direct')", @click="openDM") message
	bunt-button.btn-dm(v-if="hasPermission('world:chat.direct')", @click="openDM") call
	bunt-button.btn-dm(v-if="hasPermission('world:chat.direct')", @click="openDM") block
	template(v-if="$features.enabled('chat-moderation') && hasPermission('room:chat.moderate') && sender.id !== user.id")
		.moderation-state {{ sender.moderation_state }}
		.actions
			bunt-button.btn-reactivate(
				v-if="sender.moderation_state",
				:loading="moderating === 'reactivate'",
				:error-message="(moderationError && moderationError.action === 'reactivate') ? moderationError.message : null",
				@click="moderateAction('reactivate')", :key="`${sender.id}-reactivate`")
				| {{ sender.moderation_state === 'banned' ? 'unban' : 'unsilence'}}
			bunt-button.btn-ban(
				v-if="sender.moderation_state !== 'banned'",
				:loading="moderating === 'ban'",
				:error-message="(moderationError && moderationError.action === 'ban') ? moderationError.message : null",
				@click="moderateAction('ban')", :key="`${sender.id}-ban`")
				| ban
			bunt-button.btn-silence(
				v-if="!sender.moderation_state",
				:loading="moderating === 'silence'",
				:error-message="(moderationError && moderationError.action === 'silence') ? moderationError.message : null",
				@click="moderateAction('silence')", :key="`${sender.id}-silence`")
				| silence
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import Avatar from 'components/Avatar'

export default {
	props: {
		sender: Object,
	},
	components: { Avatar },
	data () {
		return {
			moderating: false,
			moderationError: null
		}
	},
	computed: {
		...mapState(['user']),
		...mapGetters(['hasPermission']),
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
		.btn-reactivate
			button-style(style: clear, color: $clr-success, text-color: $clr-success)
		.btn-ban
			button-style(style: clear, color: $clr-danger, text-color: $clr-danger)
		.btn-silence
			button-style(style: clear, color: $clr-deep-orange, text-color: $clr-deep-orange)
</style>

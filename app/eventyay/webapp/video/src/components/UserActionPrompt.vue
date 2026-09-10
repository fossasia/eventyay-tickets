<template lang="pug">
prompt.c-user-action-prompt(@close="$emit('close')", :class="[`action-${action}`]")
	.content
		h2(v-if="success") {{ confirmationText }}
		h2(v-else) {{ questionText }}
		.user
			avatar(:user="user", :size="64")
			.display-name
				| {{ user.profile.display_name }}
				.ui-badge(v-for="badge in user.badges") {{ badge }}
		.explanation {{ explanationText }}
		.actions
			bunt-button.btn-cancel(v-if="!success", @click="$emit('close')") {{ $t('cancel') }}
			bunt-button.btn-action(@click="takeAction", :loading="loading", :error-message="error") {{ executeText }}
</template>
<script>
import Prompt from 'components/Prompt'
import Avatar from 'components/Avatar'

export default {
	components: { Prompt, Avatar },
	props: {
		user: Object,
		action: String, // block, ban, silence, reactivate
		closeDelay: {
			type: Number,
			default: 2500
		}
	},
	emits: ['close'],
	data() {
		return {
			loading: false,
			error: null,
			success: false
		}
	},
	computed: {
		actionLabel() {
			if (this.action === 'reactivate') {
				return this.user.moderation_state === 'banned' ? 'unban' : 'unsilence'
			}
			return this.action
		},
		questionText() {
			switch (this.actionLabel) {
				case 'ban': return this.$t('Ban this user from the event?')
				case 'silence': return this.$t('Silence this user?')
				case 'unban': return this.$t('Unban this user?')
				case 'unsilence': return this.$t('Unsilence this user?')
				default: return this.$t('Block this user?')
			}
		},
		explanationText() {
			switch (this.actionLabel) {
				case 'ban': return this.$t('They will no longer be able to join this event.')
				case 'silence': return this.$t('They can still watch, but can no longer send chat messages.')
				case 'unban': return this.$t('They will be able to join this event again.')
				case 'unsilence': return this.$t('They will be able to send chat messages again.')
				default: return this.$t('They will no longer be able to send you direct messages.')
			}
		},
		executeText() {
			switch (this.actionLabel) {
				case 'ban': return this.$t('Ban')
				case 'silence': return this.$t('Silence')
				case 'unban': return this.$t('Unban')
				case 'unsilence': return this.$t('Unsilence')
				default: return this.$t('Block')
			}
		},
		confirmationText() {
			switch (this.actionLabel) {
				case 'ban': return this.$t('User banned')
				case 'silence': return this.$t('User silenced')
				case 'unban': return this.$t('User unbanned')
				case 'unsilence': return this.$t('User unsilenced')
				default: return this.$t('User blocked')
			}
		},
	},
	methods: {
		async takeAction() {
			this.error = null
			this.loading = true
			try {
				const successLabels = {
					block: 'blocked',
					ban: 'banned',
					silence: 'silenced',
					reactivate: this.user.moderation_state === 'banned' ? 'unbanned' : 'unsilenced'
				}
				if (this.action === 'block') {
					await this.$store.dispatch('chat/blockUser', {user: this.user})
				} else {
					await this.$store.dispatch('chat/moderateUser', {action: this.action, user: this.user})
				}
				this.success = successLabels[this.action]
				setTimeout(() => this.$emit('close'), this.closeDelay)
			} catch (error) {
				console.error('UserActionPrompt failed', error)
				this.error = error?.message || this.$t('Something went wrong.')
			}
			this.loading = false
		}
	}
}
</script>
<style lang="stylus">
.c-user-action-prompt
	.content
		display: flex
		flex-direction: column
		padding: 16px
		h2
			margin: 16px 0 0 16px
		.user
			display: flex
			align-items: center
			margin: 0 0 0 8px
			.display-name
				font-size: 24px
				margin-left: 8px
		.explanation
			margin: 16px 16px 32px 16px
		.actions
			align-self: flex-end
			.btn-cancel
				button-style(style: clear)
				margin-right: 8px
	&.action-ban, &.action-block, &.action-delete
		.btn-action
			button-style(color: $clr-danger)
	&.action-silence .btn-action
		button-style(color: $clr-deep-orange)
	&.action-reactivate, &.action-unblock
		.btn-action
			button-style(color: $clr-success)
</style>

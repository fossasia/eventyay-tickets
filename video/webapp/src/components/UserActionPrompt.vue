<template lang="pug">
prompt.c-user-action-prompt(@close="$emit('close')", :class="[`action-${action}`]")
	.content
		h2(v-if="success") {{ $t(`UserActionPrompt:action.${actionLabel}:confirmation`) }}
		h2(v-else) {{ $t(`UserActionPrompt:action.${actionLabel}:question`) }}
		.user
			avatar(:user="user", :size="128")
			.display-name
				| {{ user.profile.display_name }}
				.ui-badge(v-for="badge in user.badges") {{ badge }}
		.explanation {{ $t(`UserActionPrompt:action.${actionLabel}:explanation`) }}
		.actions
			bunt-button.btn-cancel(v-if="!success", @click="$emit('close')") {{ $t(`Prompt:cancel:label`) }}
			bunt-button.btn-action(@click="takeAction", :loading="loading", :error-message="error") {{ $t(`UserActionPrompt:action.${actionLabel}:execute:label`) }}
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
	data () {
		return {
			loading: false,
			error: null,
			success: false
		}
	},
	computed: {
		actionLabel () {
			if (this.action === 'reactivate') {
				return this.user.moderation_state === 'banned' ? 'unban' : 'unsilence'
			}
			return this.action
		}
	},
	methods: {
		async takeAction () {
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
				console.log(error)
				this.error = this.$t(`error:${error.code}`)
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
	&.action-ban, &.action-block
		.btn-action
			button-style(color: $clr-danger)
	&.action-silence .btn-action
		button-style(color: $clr-deep-orange)
	&.action-reactivate, &.action-unblock
		.btn-action
			button-style(color: $clr-success)
</style>

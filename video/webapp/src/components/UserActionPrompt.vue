<template lang="pug">
prompt.c-user-action-prompt(@close="$emit('close')", :class="[`action-${action}`]")
	.content
		.user-question
			avatar(:user="user", :size="128")
			h2(v-if="success")
				i {{ user.profile.display_name }}
				div has been {{ success }}
			h2(v-else)
				span.action {{ actionLabel }}
				i  {{ user.profile.display_name }}
				|  ?
		p This will have CONSEQUENCES!
		.actions
			bunt-button.btn-cancel(v-if="!success", @click="$emit('close')") cancel
			bunt-button.btn-action(@click="takeAction", :loading="loading", :error-message="error") {{ actionLabel }}
</template>
<script>
import Prompt from 'components/Prompt'
import Avatar from 'components/Avatar'

export default {
	props: {
		user: Object,
		action: String // block, ban, silence, reactivate
	},
	components: { Prompt, Avatar },
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
		},
		successLabel () {

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

				} else {
					await this.$store.dispatch('chat/moderateUser', {action: this.action, user: this.user})
				}
				this.success = successLabels[this.action]
				setTimeout(() => this.$emit('close'), 2500)
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
		.user-question
			display: flex
			align-items: center
			h2
				margin-left: 16px
				.action
					text-transform: capitalize
		.actions
			align-self: flex-end
			.btn-cancel
				button-style(style: clear)
				margin-right: 8px
	&.action-ban .btn-action
		button-style(color: $clr-danger)
	&.action-silence .btn-action
		button-style(color: $clr-deep-orange)
	&.action-reactivate .btn-action
		button-style(color: $clr-success)
</style>

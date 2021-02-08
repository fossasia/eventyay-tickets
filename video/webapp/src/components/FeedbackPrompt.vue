<template lang="pug">
prompt.c-feedback-prompt(@close="$emit('close')")
	.content
		h1 {{ $t('FeedbackPrompt:headline:text') }}
		p {{ $t('FeedbackPrompt:intro:text') }}
		form(@submit.prevent="submit")
			bunt-input-outline-container(:label="$t('FeedbackPrompt:message:label')")
				textarea(v-model="message", slot-scope="{focus, blur}", @focus="focus", @blur="blur")
			p.privacy {{ $t('FeedbackPrompt:privacy:text') }}
			bunt-button(type="submit", :loading="loading") {{ $t('FeedbackPrompt:submit:label') }}
</template>
<script>
import Prompt from 'components/Prompt'
import config from 'config'

export default {
	components: { Prompt },
	props: {
		module: String,
		collectTrace: Function,
	},
	data () {
		return {
			loading: false,
			message: '',
		}
	},
	methods: {
		async submit () {
			this.loading = true
			const response = await fetch(config.api.feedback, {
				method: 'POST',
				body: JSON.stringify({
					module: this.module,
					message: this.message,
					trace: JSON.stringify({
						userAgent: navigator.userAgent,
						trace: this.collectTrace()
					})
				}),
				headers: {
					'Content-Type': 'application/json',
				}
			})
			await response.json()
			// TODO error handling
			this.loading = false
			this.$emit('close')
		}
	}
}
</script>
<style lang="stylus">
.c-feedback-prompt
	.content
		display: flex
		flex-direction: column
		padding: 32px
		position: relative
		#btn-close
			icon-button-style(style: clear)
			position: absolute
			top: 8px
			right: 8px
		h1
			margin: 0
			text-align: center
		p.privacy
			color: $clr-secondary-text-light
		form
			display: flex
			flex-direction: column
			align-self: stretch
			.bunt-button
				themed-button-primary()
				margin-top: 16px
			.bunt-input-outline-container
				textarea
					background-color: transparent
					border: none
					outline: none
					resize: vertical
					min-height: 64px
					padding: 0 8px
</style>

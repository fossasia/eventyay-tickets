<template lang="pug">
prompt.c-create-dm-prompt(:scrollable="false", @close="$emit('close')")
	.content
		h1 {{ $t('CreateDMPrompt:headline:text') }}
		p {{ $t('CreateDMPrompt:intro:text') }}
		user-select(:button-label="$t('CreateDMPrompt:create-button:label')", @selected="create")
</template>
<script>
import {mapGetters} from 'vuex'
import Prompt from 'components/Prompt'
import UserSelect from 'components/UserSelect'

export default {
	components: { Prompt, UserSelect },
	data () {
		return {
			selectedUser: null
		}
	},
	computed: {
		...mapGetters(['hasPermission'])
	},
	methods: {
		async create (users) {
			// TODO error handling, progress
			await this.$store.dispatch('chat/openDirectMessage', {users: users})
			this.$emit('close')
		}
	}
}
</script>
<style lang="stylus">
.c-create-dm-prompt
	.prompt-wrapper
		height: 80vh
		width: 600px
	.content
		display: flex
		flex-direction: column
		position: relative
		box-sizing: border-box
		min-height: 0
		#btn-close
			icon-button-style(style: clear)
			position: absolute
			top: 8px
			right: 8px
		h1
			font-size: 24px
			margin: 16px 16px 8px 16px
		p
			margin: 0 16px 16px 16px
			color: $clr-secondary-text-light
		form
			display: flex
			flex-direction: column
			align-self: stretch
			.bunt-button
				themed-button-primary()
				margin-top: 16px
			.bunt-select
				select-style(size: compact)
				ul li
					display: flex
					.mdi
						margin-right: 8px
			.bunt-input-outline-container
				textarea
					background-color: transparent
					border: none
					outline: none
					resize: vertical
					min-height: 64px
					padding: 0 8px
</style>

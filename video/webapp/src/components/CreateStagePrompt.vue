<template lang="pug">
prompt.c-create-stage-prompt(@close="$emit('close')")
	.content
		bunt-icon-button#btn-close(@click="$emit('close')") close
		h1 {{ $t('CreateStagePrompt:headline:text') }}
		form(@submit.prevent="create")
			bunt-input(name="name", :label="$t('CreateStagePrompt:name:label')", icon="theater", :placeholder="$t('CreateStagePrompt:name:placeholder')")
			bunt-button(type="submit") {{ $t('CreateStagePrompt:submit:label') }}
</template>
<script>
import Prompt from 'components/Prompt'

export default {
	components: { Prompt },
	data () {
		return {
		}
	},
	computed: {},
	created () {},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {
		create () {

		}
	}
}
</script>
<style lang="stylus">
.c-create-stage-prompt
	.content
		display: flex
		flex-direction: column
		padding: 32px
		position: relative
		h1
			margin: 0
			text-align: center
		p
			max-width: 320px
		form
			display: flex
			flex-direction: column
			align-self: stretch
			.bunt-button
				themed-button-primary()
</style>

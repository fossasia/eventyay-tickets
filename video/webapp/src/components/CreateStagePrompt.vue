<template lang="pug">
prompt.c-create-stage-prompt(@close="$emit('close')")
	.content
		h1 {{ $t('CreateStagePrompt:headline:text') }}
		form(@submit.prevent="create")
			bunt-input(name="name", :label="$t('CreateStagePrompt:name:label')", icon="theater", :placeholder="$t('CreateStagePrompt:name:placeholder')", v-model="name", :validation="$v.name")
			bunt-input(name="url", :label="$t('CreateStagePrompt:url:label')", icon="link", placeholder="https://example.com/stream.m3u8", v-model="url", :validation="$v.url")
			bunt-input-outline-container(:label="$t('CreateChatPrompt:description:label')")
				textarea(v-model="description", slot-scope="{focus, blur}", @focus="focus", @blur="blur")
			bunt-button(type="submit", :loading="loading", :error-message="error") {{ $t('CreateStagePrompt:submit:label') }}
</template>
<script>
import Prompt from 'components/Prompt'
import { required, url } from 'lib/validators'

export default {
	components: { Prompt },
	data () {
		return {
			name: '',
			url: '',
			description: '',
			loading: false,
			error: null
		}
	},
	validations: {
		url: {
			required: required('HLS URL is required'),
			url: url('must be a valid url')
		},
		name: {
			required: required('Name is required')
		}
	},
	methods: {
		async create () {
			this.error = null
			this.$v.$touch()
			if (this.$v.$invalid) return

			this.loading = true
			const modules = []
			modules.push({
				type: 'chat.native',
				config: {
					volatile: true,
				}
			})
			modules.push({
				type: 'livestream.native',
				config: {
					hls_url: this.url,
				}
			})
			let room
			try {
				({ room } = await this.$store.dispatch('createRoom', {
					name: this.name,
					description: this.description,
					modules
				}))
				this.loading = false
				this.$router.push({name: 'room', params: {roomId: room}})
				this.$emit('close')
			} catch (error) {
				console.log(error)
				this.loading = false
				this.error = error.message || error
			}
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
			.bunt-input-outline-container
				margin-top: 16px
				textarea
					background-color: transparent
					border: none
					outline: none
					resize: vertical
					min-height: 64px
					padding: 0 8px
			.bunt-button
				themed-button-primary()
				margin-top: 16px
</style>

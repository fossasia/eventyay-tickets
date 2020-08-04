<template lang="pug">
prompt.c-create-stage-prompt(@close="$emit('close')")
	.content
		bunt-icon-button#btn-close(@click="$emit('close')") close
		h1 {{ $t('CreateStagePrompt:headline:text') }}
		form(@submit.prevent="create")
			bunt-input(name="name", :label="$t('CreateStagePrompt:name:label')", icon="theater", :placeholder="$t('CreateStagePrompt:name:placeholder')", v-model="name", :validation="$v.name")
			bunt-input(name="url", :label="$t('CreateStagePrompt:url:label')", icon="link", placeholder="https://example.com/stream.m3u8", v-model="url", :validation="$v.url")
			bunt-button(type="submit", :loading="loading") {{ $t('CreateStagePrompt:submit:label') }}
</template>
<script>
import Prompt from 'components/Prompt'
import { required, url } from 'vuelidate/lib/validators'

export default {
	components: { Prompt },
	data () {
		return {
			name: '',
			url: '',
			loading: false
		}
	},
	validations: {
		url: {
			required, url
		},
		name: {
			required
		}
	},
	computed: {},
	created () {},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {
		async create () {
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
			const { room } = await this.$store.dispatch('createRoom', {
				name: this.name,
				modules
			})
			// TODO error handling
			this.loading = false
			this.$router.push({name: 'room', params: {roomId: room}})
			this.$emit('close')
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

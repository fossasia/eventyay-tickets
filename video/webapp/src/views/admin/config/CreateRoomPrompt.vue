<template lang="pug">
prompt.c-create-room-prompt(@close="$emit('close')")
	.content
		h1 {{ $t('CreateRoomPrompt:headline:text') }}
		form(@submit.prevent="create")
			bunt-input(name="name", :label="$t('CreateRoomPrompt:name:label')", :placeholder="$t('CreateRoomPrompt:name:placeholder')", v-model="name", :validation="$v.name")
			bunt-button(type="submit", :loading="loading", :error-message="error") {{ $t('CreateRoomPrompt:submit:label') }}
</template>
<script>
import Prompt from 'components/Prompt'
import { required } from 'lib/validators'

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
			let room
			try {
				({ room } = await this.$store.dispatch('createRoom', {
					name: this.name,
					description: this.description,
					modules: []
				}))
				this.loading = false
				this.$router.push({name: 'admin:room', params: {editRoomId: room}})
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
.c-create-room-prompt
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
				margin-top: 16px
</style>

<template lang="pug">
.c-upload-url-input
	bunt-input(v-model="value", :label="label", :name="name", :validation="validation")
	.file-selector
		bunt-icon-button(:loading="uploading") upload
		input(type="file", @change="upload", ref="fileInput")

</template>
<script>
import config from 'config'

export default {
	props: {
		value: String,
		label: String,
		name: String,
		validation: Object,
	},
	data () {
		return {
			uploading: false,
		}
	},
	methods: {
		upload () {
			const data = new FormData()
			var file = this.$refs.fileInput.files[0]
			data.append('file', file)

			const headers = new Headers()
			if (this.$store.state.token) {
				headers.append('Authorization', `Bearer ${this.$store.state.token}`)
			} else if (this.$store.state.clientId) {
				headers.append('Authorization', `Client ${this.$store.state.clientId}`)
			}
			this.uploading = true
			fetch(config.api.upload, {
				method: 'POST',
				headers: headers,
				body: data
			}).then(response => response.json()).then(data => {
				this.value = data.url
				this.$emit('input', this.value)
				this.uploading = false
			}).catch(error => {
				// TODO: better error handling
				console.log(error)
				alert(`error: ${error}`)
				this.uploading = false
			})
		}
	},
}
</script>
<style lang="stylus">
	.c-upload-url-input
		display: flex
		align-items: center

		.bunt-input
			flex-grow: 1

		.file-selector
			flex-grow: 0
			position: relative

			input
				opacity: 0
				cursor: pointer
				position: absolute
				width: 100%
				height: 100%
				top: 0
				left: 0
</style>

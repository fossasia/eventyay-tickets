<template lang="pug">
.c-upload-url-input
	bunt-input(:value="value", :label="label", :name="name", :validation="validation", @input="update($event)")
	bunt-progress-circular(v-if="uploading", size="small")
	.file-selector(v-else)
		bunt-icon-button upload
		input(ref="fileInput", type="file", :accept="accept", @change="upload")

</template>
<script>
import api from 'lib/api'

export default {
	props: {
		value: String,
		label: String,
		name: String,
		validation: Object,
		uploadUrl: String,
		accept: {
			type: String,
			default: 'image/png, .png, image/jpg, .jpg, .jpeg, image/gif, .gif, application/pdf, .pdf, image/svg+xml, .svg, video/mp4, video/mpeg, .mp4, video/webm, audio/webm, .webm, audio/mp3, audio/mpeg, .mp3'
		}
	},
	data () {
		return {
			uploading: false,
		}
	},
	methods: {
		update (val) {
			this.$emit('input', val)
		},
		upload () {
			var file = this.$refs.fileInput.files[0]

			api.uploadFilePromise(file, file.name, this.uploadUrl).then(data => {
				if (data.error) {
					alert(`Upload error: ${data.error}`) // Proper user-friendly messages
					this.$emit('input', '')
				} else {
					this.$emit('input', data.url)
				}
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
		.bunt-progress-circular.small
			margin: 0 6px
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

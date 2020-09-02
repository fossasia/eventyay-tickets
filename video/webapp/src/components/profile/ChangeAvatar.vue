<template lang="pug">
.c-change-avatar
	.inputs
		bunt-button.btn-randomize(@click="changeIdenticon") randomize
		p or
		upload-button.btn-upload(@change="fileSelected", accept="image/png, image/jpg") upload
	.image-wrapper
		cropper(v-if="avatarImage", ref="cropper", classname="cropper", stencil-component="circle-stencil", :src="avatarImage", :stencil-props="{aspectRatio: '1/1'}")
		identicon(v-else, :id="value.identicon", @click.native="changeIdenticon")
</template>
<script>
// TODO repeating this step makes the avatar smaller
import { v4 as uuid } from 'uuid'
import { Cropper, CircleStencil } from 'vue-advanced-cropper'
import api from 'lib/api'
import Identicon from 'components/Identicon'
import UploadButton from 'components/UploadButton'

const MAX_AVATAR_SIZE = 128

export default {
	components: { Cropper, CircleStencil, Identicon, UploadButton },
	props: {
		value: Object
	},
	data () {
		return {
			avatarImage: null,
		}
	},
	created () {
		if (this.value.url) {
			this.avatarImage = this.value.url
		}
	},
	methods: {
		changeIdenticon () {
			this.avatarImage = null
			this.$emit('input', {identicon: uuid()})
		},
		fileSelected () {
			// TODO block reupload while running?
			if (!event.target.files.length === 1) return
			const avatarFile = event.target.files[0]
			const reader = new FileReader()
			reader.readAsDataURL(avatarFile)
			reader.onload = event => {
				if (event.target.readyState !== FileReader.DONE) return
				this.avatarImage = event.target.result
			}
		},
		update () {
			return new Promise((resolve, reject) => {
				if (!this.$refs.cropper) return resolve()
				const { canvas } = this.$refs.cropper.getResult()
				if (!canvas) return resolve()
				const resizeCanvas = document.createElement('canvas')
				resizeCanvas.width = MAX_AVATAR_SIZE
				resizeCanvas.height = MAX_AVATAR_SIZE

				var ctx = resizeCanvas.getContext('2d')
				ctx.drawImage(canvas, 0, 0, canvas.width, canvas.height, 0, 0, MAX_AVATAR_SIZE, MAX_AVATAR_SIZE)
				resizeCanvas.toBlob(blob => {
					const request = api.uploadFile(blob, 'avatar.png')
					request.addEventListener('load', (event) => {
						const response = JSON.parse(request.responseText)
						this.$emit('input', {url: response.url})
						resolve()
					})
				}, 'image/png') // TODO use original mimetype
			})
		},
	}
}
</script>
<style lang="stylus">
.c-change-avatar
	.c-identicon
		cursor: pointer
		height: 128px
		width: 128px
		margin: 96px 0
	.inputs
		display: flex
		justify-content: center
		align-items: center
		margin-bottom: 16px
		p
			margin: 0 28px 0 16px
	.btn-randomize
		themed-button-secondary()
	.btn-upload .bunt-button
		themed-button-primary()
	.image-wrapper
		flex: auto
		display: flex
		flex-direction: column
		align-items: center
		justify-content: center
	.cropper
		width: 320px
		height: 320px
		background-color: $clr-grey-900
</style>

<template lang="pug">
.c-change-avatar(v-if="value")
	.inputs
		bunt-button.btn-randomize(@click="changeIdenticon") {{ $t('profile/ChangeAvatar:button-randomize:label') }}
		span {{ $t('profile/ChangeAvatar:or') }}
		upload-button.btn-upload(@change="fileSelected", accept="image/png, image/jpg, .png, .jpg, .jpeg") {{ $t('profile/ChangeAvatar:button-upload:label') }}
	.image-wrapper
		.file-error(v-if="fileError")
			.mdi.mdi-alert-octagon
			.message {{ fileError }}
		cropper(v-else-if="avatarImage", ref="cropper", classname="cropper", stencil-component="circle-stencil", :src="avatarImage", :stencil-props="{aspectRatio: '1/1'}", :restrictions="pixelsRestrictions")
		identicon(v-else, :id="identicon", @click.native="changeIdenticon")
</template>
<script>
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
			identicon: null,
			avatarImage: null,
			fileError: null,
			changedImage: false
		}
	},
	created () {
		if (!this.value) {
			this.$emit('input', {})
			this.identicon = uuid()
		} else if (this.value.url) {
			this.avatarImage = this.value.url
		} else if (this.value.identicon) {
			this.identicon = this.value.identicon
		}
	},
	methods: {
		changeIdenticon () {
			this.fileError = null
			this.avatarImage = null
			this.identicon = uuid()
			this.$emit('blockSave', false)
		},
		fileSelected (event) {
			// TODO block reupload while running?
			this.fileError = null
			this.avatarImage = null
			this.$emit('blockSave', false)
			if (!event.target.files.length === 1) return
			const avatarFile = event.target.files[0]
			const reader = new FileReader()
			reader.readAsDataURL(avatarFile)
			event.target.value = ''
			reader.onload = event => {
				if (event.target.readyState !== FileReader.DONE) return
				const img = new Image()
				img.onload = () => {
					if (img.width < 128 || img.height < 128) {
						this.fileError = this.$t('profile/ChangeAvatar:error:image-too-small')
						this.$emit('blockSave', true)
					} else {
						this.changedImage = true
						this.avatarImage = event.target.result
					}
				}
				img.src = event.target.result
			}
		},
		pixelsRestrictions ({minWidth, minHeight, maxWidth, maxHeight, imageWidth, imageHeight}) {
			return {
				minWidth: Math.max(128, minWidth),
				minHeight: Math.max(128, minHeight),
				maxWidth: maxWidth,
				maxHeight: maxHeight,
			}
		},
		update () {
			return new Promise((resolve, reject) => {
				const { canvas } = this.$refs.cropper?.getResult() || {}
				if (!canvas) {
					this.$emit('input', {identicon: this.identicon})
					return resolve()
				}
				if (!this.changedImage) return resolve()
				const resizeCanvas = document.createElement('canvas')
				resizeCanvas.width = MAX_AVATAR_SIZE
				resizeCanvas.height = MAX_AVATAR_SIZE

				const ctx = resizeCanvas.getContext('2d')
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
	display: flex
	flex-direction: column
	align-items: center
	.c-identicon
		cursor: pointer
		height: 128px
		width: 128px
	.inputs
		display: flex
		justify-content: center
		align-items: center
		margin-bottom: 16px
		> span
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
		height: calc(80vh - 230px) // HACK approx. shrinking to avoid top down constraints
		max-height: 320px
		min-height: 160px
		+below('m')
			height: calc(95vh - 230px)
	.file-error
		width: 320px
		height: 320px
		display: flex
		flex-direction: column
		color: $clr-danger
		align-items: center
		justify-content: center
		.mdi
			font-size: 64px
	.cropper
		width: 320px
		height: 320px
		background-color: $clr-grey-900
</style>

<template lang="pug">
.c-change-avatar(v-if="modelValue")
	.inputs
		bunt-button.btn-randomize(@click="changeIdenticon") {{ $t('profile/ChangeAvatar:button-randomize:label') }}
		span {{ $t('profile/ChangeAvatar:or') }}
		upload-button.btn-upload(@change="fileSelected", accept="image/png, image/jpg, .png, .jpg, .jpeg") {{ $t('profile/ChangeAvatar:button-upload:label') }}
	.image-wrapper
		.file-error(v-if="fileError")
			.mdi.mdi-alert-octagon
			.message {{ fileError }}
		Cropper(v-else-if="avatarImage", ref="cropperRef", class="cropper", :stencilComponent="CircleStencil", :src="avatarImage", :stencilProps="{aspectRatio: '1/1'}", :sizeRestrictionsAlgorithm="pixelsRestrictions")
		identicon(v-else, :user="identiconUser", @click="changeIdenticon")
</template>
<script setup>
import { ref, computed, onMounted, getCurrentInstance, nextTick } from 'vue'
import { v4 as uuid } from 'uuid'
import { Cropper, CircleStencil } from 'vue-advanced-cropper'
import 'vue-advanced-cropper/dist/style.css'
import api from 'lib/api'
import Identicon from 'components/Identicon'
import UploadButton from 'components/UploadButton'

const MAX_AVATAR_SIZE = 128

// Props & Emits
const props = defineProps({
	modelValue: Object,
	profile: Object,
})
const emit = defineEmits(['update:modelValue', 'blockSave'])

// Globals
const { proxy } = getCurrentInstance()

// State
const identiconValue = ref(null)
const avatarImage = ref(null)
const fileError = ref(null)
const changedImage = ref(false)
const cropperRef = ref(null)

// Derived
const identiconUser = computed(() => ({
	profile: {
		...props.profile,
		avatar: { identicon: identiconValue.value },
	},
}))

// Actions
function changeIdenticon() {
	fileError.value = null
	avatarImage.value = null
	identiconValue.value = uuid()
	emit('blockSave', false)
}

function fileSelected(event) {
	fileError.value = null
	avatarImage.value = null
	emit('blockSave', false)
	if (event.target.files.length !== 1) return
	const avatarFile = event.target.files[0]
	const reader = new FileReader()
	reader.readAsDataURL(avatarFile)
	event.target.value = ''
	reader.onload = (readerEvent) => {
		if (readerEvent.target.readyState !== FileReader.DONE) return
		const img = new Image()
		img.onload = () => {
			if (img.width < 128 || img.height < 128) {
				fileError.value = proxy.$t('profile/ChangeAvatar:error:image-too-small')
				emit('blockSave', true)
			} else {
				changedImage.value = true
				nextTick(() => {
					avatarImage.value = readerEvent.target.result
				})
			}
		}
		img.src = readerEvent.target.result
	}
}

function pixelsRestrictions({ minWidth, minHeight, maxWidth, maxHeight }) {
	return {
		minWidth: Math.max(128, minWidth),
		minHeight: Math.max(128, minHeight),
		maxWidth,
		maxHeight,
	}
}

function update() {
		return new Promise((resolve) => {
			const { canvas } = cropperRef.value?.getResult() || {}
		if (!canvas) {
			emit('update:modelValue', { identicon: identiconValue.value })
			return resolve()
		}
		if (!changedImage.value) return resolve()

		canvas.toBlob((blob) => {
			const request = api.uploadFile(blob, 'avatar.png', null, MAX_AVATAR_SIZE, MAX_AVATAR_SIZE)
			request.addEventListener('load', () => {
				const response = JSON.parse(request.responseText)
				emit('update:modelValue', { url: response.url })
				resolve()
			})
		}, 'image/png')
	})
}

onMounted(() => {
	if (!props.modelValue) {
		emit('update:modelValue', {})
		identiconValue.value = uuid()
	} else if (props.modelValue.url) {
		avatarImage.value = props.modelValue.url
	} else if (props.modelValue.identicon) {
		identiconValue.value = props.modelValue.identicon
	}
})

// Expose for parent refs
defineExpose({ update })
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

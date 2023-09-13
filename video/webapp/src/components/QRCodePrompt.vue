<template lang="pug">
prompt.c-qrcode-prompt(@close="$emit('close')")
	.content
		bunt-icon-button#btn-close(@click="$emit('close')") close
		h1 {{ $t('QRCodePrompt:title') }}
		bunt-progress-circular(v-if="!url")
		template(v-else)
			a.download(:href="downloadUrl", :download="`anonymous-link-room-${room.name}.svg`")
				.svg(v-html="qrcode")
				| {{ $t('QRCodePrompt:download-svg') }}
			CopyableText.url(:text="shortUrl")
</template>
<script>
import QRCode from 'qrcode'
import api from 'lib/api'
import CopyableText from 'components/CopyableText'
import Prompt from 'components/Prompt'

export default {
	components: { CopyableText, Prompt },
	props: {
		room: Object
	},
	data () {
		return {
			url: null,
			qrcode: null
		}
	},
	computed: {
		shortUrl () {
			return this.url.replace(/^https?:\/\//, '')
		},
		downloadUrl () {
			return `data:image/svg+xml;base64,${btoa(this.qrcode)}`
		}
	},
	async created () {
		const { url } = await api.call('room.invite.anonymous.link', {room: this.room.id})
		this.url = url
		this.qrcode = await QRCode.toString(this.url, {type: 'svg', margin: 1})
	}
}
</script>
<style lang="stylus">
.c-qrcode-prompt
	.prompt-wrapper
		width: 640px
	.content
		display: flex
		flex-direction: column
		padding: 32px
		position: relative
		align-items: center
		h1
			margin: 0
			text-align: center
		.bunt-progress-circular
			margin: auto
		a
			text-align: center
		svg
			width: 520px
		.url
			margin: 16px
			font-size: 24px
</style>

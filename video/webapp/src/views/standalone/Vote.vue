<template lang="pug">
.c-standalone-vote
	h1 Vote now here:
	.svg(v-html="qrcode")
	.url {{ url }}
</template>
<script>
import QRCode from 'qrcode'

export default {
	components: {},
	props: {
		room: Object
	},
	data () {
		return {
			qrcode: null
		}
	},
	computed: {
		url () {
			return 'vle.ss/AB12'
		},
		fullUrl () {
			return `https://${this.url}`
		}
	},
	async mounted () {
		this.qrcode = await QRCode.toString(this.url, {type: 'svg'})
	}
}
</script>
<style lang="stylus">
.c-standalone-vote
	display: flex
	flex-direction: column
	align-items: center
	.svg
		width: 500px
		svg
			// hide white background
			:first-child
				display: none
	.url
		font-size: 48px

	.themed-bg &
		svg
			path
					stroke: var(--clr-standalone-fg)
</style>

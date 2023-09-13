<template lang="pug">
.c-standalone-vote(v-if="linkCache")
	h1 Vote now here:
	.svg(v-html="linkCache.qrcode")
	.url {{ linkCache.shortUrl }}
</template>
<script>
import QRCode from 'qrcode'
import api from 'lib/api'
let linkCache

export default {
	components: {},
	props: {
		room: Object
	},
	data () {
		return {
			linkCache
		}
	},
	async created () {
		if (!linkCache || linkCache.room !== this.room) {
			const { url } = await api.call('room.invite.anonymous.link', {room: this.room.id})
			linkCache = {
				room: this.room,
				url,
				shortUrl: url.replace(/^https?:\/\//, ''),
				qrcode: await QRCode.toString(url, {type: 'svg'})
			}
		}
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

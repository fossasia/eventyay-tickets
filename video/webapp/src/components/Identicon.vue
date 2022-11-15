<template lang="pug">
img.c-identicon(:src="url")
</template>
<script>
import theme from 'theme'
import { renderUrl as renderIdenticonUrl } from 'lib/identicons'

export default {
	props: {
		user: Object,
		identiconStyle: {
			type: String,
			default: theme.identicons.style
		}
	},
	computed: {
		url () {
			return renderIdenticonUrl(this.user, this.identiconStyle)
		}
	}
}
</script>
<style lang="stylus">
.c-identicon
	user-select: none
</style>

<template lang="pug">
img.c-identicon(:src="url")
</template>
<script>
import { getIdenticonSvgUrl } from 'lib/identicon'

export default {
	props: {
		id: String
	},
	computed: {
		url () {
			return getIdenticonSvgUrl(this.id)
		}
	}
}
</script>
<style lang="stylus">
.c-identicon
	user-select: none
</style>

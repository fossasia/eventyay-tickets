<template lang="pug">
.c-static-page(v-scrollbar.y="")
	rich-text-content(:content="module.config.content")
</template>
<script>
import RichTextContent from 'components/RichTextContent'

export default {
	components: { RichTextContent },
	props: {
		module: Object
	}
}
</script>
<style lang="stylus">
.c-static-page
	flex: auto
	.content-wrapper
		width: 100%
		max-width: 960px
		margin: 0 auto

	// TODO decopypaste thhis
	.rich-text-content
		margin: 16px 0
		> *
			max-width: 960px
			margin: 0 auto
			+below('m')
				margin: 0 16px
		img
			display: block
			margin: 0 auto
		.ql-full-width-true
			margin: 0
			max-width: none
</style>

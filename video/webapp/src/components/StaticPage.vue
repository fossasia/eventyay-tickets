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

	.rich-text-content
		margin: 16px 32px
</style>

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
	.rich-text-content .ql-editor
		margin: 16px 0
		// TODO :has isn't supported by FF yet, but it was borked anyways.
		.ql-full-width-true:not(:has( > img))
			margin: 0 16px
#app.override-sidebar-collapse .c-static-page .rich-text-content .ql-editor
	> *, li
		margin: 0 16px
</style>

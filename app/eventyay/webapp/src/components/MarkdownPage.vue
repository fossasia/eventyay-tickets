<template lang="pug">
.c-markdown-page(v-scrollbar.y="")
	markdown-content(:markdown="module.config.content")
</template>
<script>
import MarkdownContent from 'components/MarkdownContent'

export default {
	components: { MarkdownContent },
	props: {
		module: Object
	}
}
</script>
<style lang="stylus">
.c-markdown-page
	.markdown-content
		margin: 16px 32px
</style>

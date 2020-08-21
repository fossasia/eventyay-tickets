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

	// TODO put this somewhere more generic
	table
		border-collapse: collapse
		width: 100%

	table td, table th
		border: 1px solid #ccc
		border-collapse: collapse
		padding: 10px
		text-align: left

	img
		max-width: 100%

	a:hover
			text-decoration: underline
</style>

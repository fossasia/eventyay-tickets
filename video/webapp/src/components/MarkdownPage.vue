<template lang="pug">
.c-home(v-scrollbar.y="")
	.content(v-html="markdownContent")
</template>
<script>
import MarkdownIt from 'markdown-it'
import sanitizeHtml from 'sanitize-html'

const markdownIt = MarkdownIt({
	breaks: true,
	html: true,
})

export default {
	props: {
		module: Object
	},
	computed: {
		markdownContent () {
			if (!this.module.config.content) return
			return sanitizeHtml(markdownIt.render(this.module.config.content), {
				transformTags: {
					a: sanitizeHtml.simpleTransform('a', {target: '_blank'}),
				},
				allowedTags: sanitizeHtml.defaults.allowedTags.concat(['img', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
			})
		}
	}
}
</script>
<style lang="stylus">
.c-home
	.content
		margin: 16px 32px

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
</style>

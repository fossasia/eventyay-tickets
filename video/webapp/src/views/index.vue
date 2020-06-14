<template lang="pug">
.c-home(v-scrollbar.y="")
	.content(v-html="markdownContent")
</template>
<script>
import { mapState } from 'vuex'
import MarkdownIt from 'markdown-it'

const markdownIt = MarkdownIt({
	breaks: true
})

export default {
	computed: {
		...mapState(['world']),
		markdownContent () {
			if (!this.world.about) return
			return markdownIt.render(this.world.about)
		}
	}
}
</script>
<style lang="stylus">
.c-home
	.content
		margin: 16px 32px
</style>

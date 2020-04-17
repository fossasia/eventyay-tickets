<template lang="pug">
.c-home
	.content(v-html="markdownContent")
</template>
<script>
import { mapState } from 'vuex'
import MarkdownIt from 'markdown-it'

const markdownIt = MarkdownIt({
	breaks: true
})
export default {
	components: {},
	data () {
		return {
		}
	},
	computed: {
		...mapState(['world']),
		markdownContent () {
			if (!this.world.about) return
			return markdownIt.render(this.world.about)
		}
	},
	created () {},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {}
}
</script>
<style lang="stylus">
.c-home
	.content
		margin: 16px 32px
</style>

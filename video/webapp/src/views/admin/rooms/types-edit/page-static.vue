<template lang="pug">
.c-page-static-settings
	rich-text-editor(v-model="modules['page.static'].config.content")
</template>
<script>
import RichTextEditor from 'components/RichTextEditor'
import mixin from './mixin'

export default {
	components: { RichTextEditor },
	mixins: [mixin],
	data () {
		return {
		}
	},
	computed: {},
	created () {},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {}
}
</script>
<style lang="stylus">
// HACK
.c-page-static-settings
	width: calc(100vw - var(--sidebar-width) - 32px)
</style>

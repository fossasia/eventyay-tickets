<template lang="pug">
.rich-text-content(v-html="renderedContent", @click="handleClick")
</template>
<script>
import Quill from 'quill'
import router from 'router'
import VideoResponsive from 'lib/quill/VideoResponsive'
import fullWidthFormat from 'lib/quill/fullWidthFormat'

export default {
	props: {
		content: Object,
	},
	computed: {
		renderedContent () {
			const tempCont = document.createElement('div')
			Quill.register(VideoResponsive)
			Quill.register(fullWidthFormat)
			const quill = new Quill(tempCont)
			quill.setContents(this.content)
			return tempCont.getElementsByClassName('ql-editor')[0].innerHTML
		},
	},
	methods: {
		handleClick (event) {
			const a = event.target.closest('a')
			if (!a) return
			// from https://github.com/vuejs/vue-router/blob/dfc289202703319cf7beb38d03c9258c806c4d62/src/components/link.js#L165
			// don't redirect with control keys
			if (event.metaKey || event.altKey || event.ctrlKey || event.shiftKey) return
			// don't redirect on right click
			if (event.button !== undefined && event.button !== 0) return
			// don't handle same page links/anchors or external links
			const url = new URL(a.href)
			if (window.location.pathname === url.pathname) return
			if (window.location.hostname !== url.hostname) return
			event.preventDefault()
			router.push(url.pathname + url.hash)
		}
	},
}
</script>
<style lang="styl">
.rich-text-content
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

	.ql-video-wrapper
		.ql-video-inner
			height: 0
			width: 100%
			padding-top: 56.25%
			position: relative

			iframe, object, embed
				position: absolute
				top: 0
				left: 0
				width: 100%
				height: 100%

	a:hover
		text-decoration: underline

	li
		line-height: 1.6

	.ql-syntax
		font-size: 1.2em

	.ql-align-center
		text-align: center

	.ql-align-right
		text-align: right
</style>

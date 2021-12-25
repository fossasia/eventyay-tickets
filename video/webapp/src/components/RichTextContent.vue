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
		content: [Array, Object],
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

	p,
	ol,
	ul,
	pre,
	blockquote,
	h1,
	h2,
	h3,
	h4,
	h5,
	h6
		margin: 0
		padding: 0
		counter-reset: list-1 list-2 list-3 list-4 list-5 list-6 list-7 list-8 list-9

	ol li
		list-style-type: none
		counter-reset: list-1 list-2 list-3 list-4 list-5 list-6 list-7 list-8 list-9
		counter-increment: list-0

	ol li:before
		content: counter(list-0, decimal) '. '

	ol li.ql-indent-1
		counter-increment: list-1

	ol li.ql-indent-1:before
		content: counter(list-1, lower-alpha) '. '

	ol li.ql-indent-1
		counter-reset: list-2 list-3 list-4 list-5 list-6 list-7 list-8 list-9

	ol li.ql-indent-2
		counter-increment: list-2

	ol li.ql-indent-2:before
		content: counter(list-2, lower-roman) '. '

	ol li.ql-indent-2
		counter-reset: list-3 list-4 list-5 list-6 list-7 list-8 list-9

	ol li.ql-indent-3
		counter-increment: list-3

	ol li.ql-indent-3:before
		content: counter(list-3, decimal) '. '

	ol li.ql-indent-3
		counter-reset: list-4 list-5 list-6 list-7 list-8 list-9

	ol li.ql-indent-4
		counter-increment: list-4

	ol li.ql-indent-4:before
		content: counter(list-4, lower-alpha) '. '

	ol li.ql-indent-4
		counter-reset: list-5 list-6 list-7 list-8 list-9

	ol li.ql-indent-5
		counter-increment: list-5

	ol li.ql-indent-5:before
		content: counter(list-5, lower-roman) '. '

	ol li.ql-indent-5
		counter-reset: list-6 list-7 list-8 list-9

	ol li.ql-indent-6
		counter-increment: list-6

	ol li.ql-indent-6:before
		content: counter(list-6, decimal) '. '

	ol li.ql-indent-6
		counter-reset: list-7 list-8 list-9

	ol li.ql-indent-7
		counter-increment: list-7

	ol li.ql-indent-7:before
		content: counter(list-7, lower-alpha) '. '

	ol li.ql-indent-7
		counter-reset: list-8 list-9

	ol li.ql-indent-8
		counter-increment: list-8

	ol li.ql-indent-8:before
		content: counter(list-8, lower-roman) '. '

	ol li.ql-indent-8
		counter-reset: list-9

	ol li.ql-indent-9
		counter-increment: list-9

	ol li.ql-indent-9:before
		content: counter(list-9, decimal) '. '

	.ql-indent-1:not(.ql-direction-rtl)
		padding-left: 3em

	li.ql-indent-1:not(.ql-direction-rtl)
		padding-left: 4.5em

	.ql-indent-1.ql-direction-rtl.ql-align-right
		padding-right: 3em

	li.ql-indent-1.ql-direction-rtl.ql-align-right
		padding-right: 4.5em

	.ql-indent-2:not(.ql-direction-rtl)
		padding-left: 6em

	li.ql-indent-2:not(.ql-direction-rtl)
		padding-left: 7.5em

	.ql-indent-2.ql-direction-rtl.ql-align-right
		padding-right: 6em

	li.ql-indent-2.ql-direction-rtl.ql-align-right
		padding-right: 7.5em

	.ql-indent-3:not(.ql-direction-rtl)
		padding-left: 9em

	li.ql-indent-3:not(.ql-direction-rtl)
		padding-left: 10.5em

	.ql-indent-3.ql-direction-rtl.ql-align-right
		padding-right: 9em

	li.ql-indent-3.ql-direction-rtl.ql-align-right
		padding-right: 10.5em

	.ql-indent-4:not(.ql-direction-rtl)
		padding-left: 12em

	li.ql-indent-4:not(.ql-direction-rtl)
		padding-left: 13.5em

	.ql-indent-4.ql-direction-rtl.ql-align-right
		padding-right: 12em

	li.ql-indent-4.ql-direction-rtl.ql-align-right
		padding-right: 13.5em

	.ql-indent-5:not(.ql-direction-rtl)
		padding-left: 15em

	li.ql-indent-5:not(.ql-direction-rtl)
		padding-left: 16.5em

	.ql-indent-5.ql-direction-rtl.ql-align-right
		padding-right: 15em

	li.ql-indent-5.ql-direction-rtl.ql-align-right
		padding-right: 16.5em

	.ql-indent-6:not(.ql-direction-rtl)
		padding-left: 18em

	li.ql-indent-6:not(.ql-direction-rtl)
		padding-left: 19.5em

	.ql-indent-6.ql-direction-rtl.ql-align-right
		padding-right: 18em

	li.ql-indent-6.ql-direction-rtl.ql-align-right
		padding-right: 19.5em

	.ql-indent-7:not(.ql-direction-rtl)
		padding-left: 21em

	li.ql-indent-7:not(.ql-direction-rtl)
		padding-left: 22.5em

	.ql-indent-7.ql-direction-rtl.ql-align-right
		padding-right: 21em

	li.ql-indent-7.ql-direction-rtl.ql-align-right
		padding-right: 22.5em

	.ql-indent-8:not(.ql-direction-rtl)
		padding-left: 24em

	li.ql-indent-8:not(.ql-direction-rtl)
		padding-left: 25.5em

	.ql-indent-8.ql-direction-rtl.ql-align-right
		padding-right: 24em

	li.ql-indent-8.ql-direction-rtl.ql-align-right
		padding-right: 25.5em

	.ql-indent-9:not(.ql-direction-rtl)
		padding-left: 27em

	li.ql-indent-9:not(.ql-direction-rtl)
		padding-left: 28.5em

	.ql-indent-9.ql-direction-rtl.ql-align-right
		padding-right: 27em

	li.ql-indent-9.ql-direction-rtl.ql-align-right
		padding-right: 28.5em

</style>

<template lang="pug">
.rich-text-content(@click="handleClick")
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
	watch: {
		content: {
			handler (val) {
				this.quill.setContents(val)
			},
			deep: true
		},
	},
	mounted () {
		Quill.register(VideoResponsive)
		Quill.register(fullWidthFormat)
		const quill = new Quill(this.$el, {
			readOnly: true
		})
		quill.setContents(this.content)
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

import MarkdownIt from 'markdown-it'
import sanitizeHtml from 'sanitize-html'
import router from 'router'

const markdownIt = MarkdownIt({
	linkify: true,
	breaks: true,
	html: true
})

markdownIt.renderer.rules.link_open = function (tokens, idx, options, env, self) {
	const [, link] = tokens[idx].attrs.find(([attr]) => attr === 'href')
	if (!link.startsWith('/')) {
		tokens[idx].attrPush(['target', '_blank'])
		tokens[idx].attrPush(['rel', 'noopener noreferrer'])
	}
	return self.renderToken(tokens, idx, options)
}

const handleClick = function (event) {
	const a = event.target.closest('a')
	if (!a || a.target === '_blank') return
	// from https://github.com/vuejs/vue-router/blob/dfc289202703319cf7beb38d03c9258c806c4d62/src/components/link.js#L165
	// don't redirect with control keys
	if (event.metaKey || event.altKey || event.ctrlKey || event.shiftKey) return
	// don't redirect on right click
	if (event.button !== undefined && event.button !== 0) return
	// don't handle same page links/anchors
	const url = new URL(a.href)
	if (window.location.pathname === url.pathname) return
	event.preventDefault()
	router.push(url.pathname + url.hash)
}

export default {
	functional: true,
	props: {
		markdown: String
	},
	render (createElement, ctx) {
		if (!ctx.props.markdown) return
		return createElement('section', {
			class: 'markdown-content rich-text-content',
			domProps: {
				innerHTML: sanitizeHtml(markdownIt.render(ctx.props.markdown), {
					allowedTags: ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'p', 'a', 'ul', 'ol', 'nl', 'li', 'b', 'i', 'strong', 'em', 'strike', 'abbr', 'code', 'hr', 'br', 'div', 'table', 'thead', 'caption', 'tbody', 'tr', 'th', 'td', 'pre', 'iframe', 'img']
				})
			},
			on: {
				click: handleClick
			}
		})
	},
}

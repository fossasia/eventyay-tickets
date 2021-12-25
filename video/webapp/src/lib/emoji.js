import data from 'emoji-mart/data/twitter.json'
import EmojiRegex from 'emoji-regex'
import { getEmojiDataFromNative as _getEmojiDataFromNative } from 'emoji-mart'
import { uncompress } from 'emoji-mart/dist-es/utils/data.js'
import MarkdownIt from 'markdown-it'

// force uncompress data, because we don't use emoji-mart methods
if (data.compressed) {
	uncompress(data)
}

const emojiRegex = EmojiRegex()
const splitEmojiRegex = new RegExp(`(${emojiRegex.source})`, 'g')
const startsWithEmojiRegex = new RegExp(`^${emojiRegex.source}`)

export function objectToCssString (object) {
	return Object.entries(object).map(([key, value]) => `${key}:${value}`).join(';')
}

export function startsWithEmoji (string) {
	return startsWithEmojiRegex.test(string)
}

export function nativeToOps (string) {
	return string.split(splitEmojiRegex).map(match => {
		if (emojiRegex.test(match)) {
			// slightly wasteful to test for emoji again
			return {insert: {emoji: match}}
		} else {
			return {insert: match}
		}
	})
}

export function getEmojiDataFromNative (native) {
	return data.emojis[_getEmojiDataFromNative(native, 'twitter', data).id]
}

export function nativeToStyle (unicodeEmoji) {
	// maps multi-codepoint emoji like 🇻🇦 / \uD83C\uDDFB\uD83C\uDDE6 => 1f1fb-1f1e6.svg
	const codepoints = Array.from(unicodeEmoji).map(c => c.codePointAt(0).toString(16))
	let src
	// drop modifiers if we don't have the full emoji
	// for example red heart => heart
	while (codepoints.length) {
		try {
			src = require(`twemoji-emojis/vendor/svg/${codepoints.join('-')}.svg`)
			break
		} catch (e) {}
		codepoints.pop()
	}

	// if we don't have the emoji, show❓
	if (!src) {
		src = require('twemoji-emojis/vendor/svg/2753.svg')
	}

	return {'background-image': `url(${src})`}
}

export function markdownEmoji (md) {
	function splitTextToken (text, Token) {
		let token
		let lastPos = 0
		const tokens = []

		text.replace(emojiRegex, function (match, offset, src) {
			// Add new tokens to pending list
			if (offset > lastPos) {
				token = new Token('text', '', 0)
				token.content = text.slice(lastPos, offset)
				tokens.push(token)
			}

			token = new Token('emoji', '', 0)
			token.content = match
			tokens.push(token)
			lastPos = offset + match.length
		})

		if (lastPos < text.length) {
			token = new Token('text', '', 0)
			token.content = text.slice(lastPos)
			tokens.push(token)
		}

		return tokens
	}
	md.core.ruler.push('emoji', function emojiReplace (state) {
		let autolinkLevel = 0

		for (const blockToken of state.tokens) {
			if (blockToken.type !== 'inline') continue
			let tokens = blockToken.children

			// We scan from the end, to keep position when new tags added.
			// Use reversed logic in links start/end match
			for (let i = tokens.length - 1; i >= 0; i--) {
				const token = tokens[i]

				if (token.type === 'link_open' || token.type === 'link_close') {
					if (token.info === 'auto') autolinkLevel -= token.nesting
				}

				if (token.type === 'text' && autolinkLevel === 0 && emojiRegex.test(token.content)) {
					// replace current node
					blockToken.children = tokens = md.utils.arrayReplaceAt(
						tokens, i, splitTextToken(token.content, state.Token)
					)
				}
			}
		}
	})
	md.renderer.rules.emoji = (tokens, idx) => {
		const isFirst = idx === 0
		const needsSpace = tokens[idx + 1] && !tokens[idx + 1].content.startsWith(' ')
		const emoji = tokens[idx].content
		return `<span class="emoji${isFirst && needsSpace ? ' needs-space' : ''}" style="${objectToCssString(nativeToStyle(emoji))}">${emoji}</span>`
	}
}

// global markdown instance to emojify plaintext
const markdownIt = MarkdownIt('zero', {})
markdownIt.use(markdownEmoji)

export function emojifyString (input) {
	if (!input) return
	return markdownIt.renderInline(input)
}

export const emojiPlugin = {
	install (Vue) {
		Vue.prototype.$emojify = emojifyString
	}
}

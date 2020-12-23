import data from 'emoji-mart/data/twitter.json'
import EmojiRegex from 'emoji-regex'
import { getEmojiDataFromNative as _getEmojiDataFromNative } from 'emoji-mart'
import { unifiedToNative } from 'emoji-mart/dist-es/utils'
import { uncompress } from 'emoji-mart/dist-es/utils/data.js'

// force uncompress data, because we don't use emoji-mart methods
if (data.compressed) {
	uncompress(data)
}

const emojiRegex = EmojiRegex()
const splitEmojiRegex = new RegExp(`(${emojiRegex.source})`, 'g')

export function getEmojiPosition (emoji) {
	if (typeof emoji === 'string') {
		emoji = data.emojis[emoji]
	}
	if (!emoji) return
	const { sheet_x: sheetX, sheet_y: sheetY } = emoji
	const multiplyX = 100 / (57 - 1)
	const multiplyY = 100 / (57 - 1)

	return `${multiplyX * sheetX}% ${multiplyY * sheetY}%`
}

export function nativeToOps (string) {
	return string.split(splitEmojiRegex).map(match => {
		const emoji = _getEmojiDataFromNative(match, 'twitter', data)
		if (emoji) {
			return {insert: {emoji: emoji.id}}
		} else {
			return {insert: match}
		}
	})
}

export function getEmojiDataFromNative (native) {
	return data.emojis[_getEmojiDataFromNative(native, 'twitter', data).id]
}

export function nativeToStyle (unicodeEmoji) {
	return {'background-position': getEmojiPosition(data.emojis[_getEmojiDataFromNative(unicodeEmoji, 'twitter', data).id])}
}

export function toNative (emojiId) {
	const emoji = data.emojis[emojiId]
	if (!emoji) return
	return unifiedToNative(emoji.unified)
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
		const emoji = data.emojis[_getEmojiDataFromNative(tokens[idx].content, 'twitter', data).id]
		return `<span class="emoji" style="background-position: ${getEmojiPosition(emoji)}"></span>`
	}
}

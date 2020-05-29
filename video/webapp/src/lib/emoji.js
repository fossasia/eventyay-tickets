import { getData } from 'emoji-mart/dist-es/utils'
import data from 'emoji-mart/data/twitter.json'
import EmojiRegex from 'emoji-regex'
import { getEmojiDataFromNative } from 'emoji-mart'

const emojiRegex = EmojiRegex()

export function getEmojiPosition (emoji) {
	const { sheet_x: sheetX, sheet_y: sheetY } = getData(emoji, 1, 'twitter', data)
	const multiplyX = 100 / (57 - 1)
	const multiplyY = 100 / (57 - 1)

	return `${multiplyX * sheetX}% ${multiplyY * sheetY}%`
}

export function getHTMLWithEmoji (content) {
	if (!content) return
	return content.replace(emojiRegex, match => {
		const emoji = getEmojiDataFromNative(match, 'twitter', data)
		return `<span class="emoji" style="background-position: ${getEmojiPosition(emoji)}"></span>`
	})
}

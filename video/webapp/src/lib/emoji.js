import { getData } from 'emoji-mart/dist-es/utils'
import data from 'emoji-mart/data/twitter.json'

export function getEmojiPosition (emoji) {
	const { sheet_x: sheetX, sheet_y: sheetY } = getData(emoji, 1, 'twitter', data)
	const multiplyX = 100 / (57 - 1)
	const multiplyY = 100 / (57 - 1)

	return `${multiplyX * sheetX}% ${multiplyY * sheetY}%`
}

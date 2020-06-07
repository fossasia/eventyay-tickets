// from https://github.com/bevacqua/fuzzysearch/blob/master/index.js
/* eslint no-labels: 0 */
export default function fuzzysearch (needle, haystack) {
	if (!needle || !haystack) return
	const hlen = haystack.length
	const nlen = needle.length
	if (nlen > hlen) {
		return false
	}
	if (nlen === hlen) {
		return needle === haystack
	}
	outer: for (let i = 0, j = 0; i < nlen; i++) {
		var nch = needle.charCodeAt(i)
		while (j < hlen) {
			if (haystack.charCodeAt(j++) === nch) {
				continue outer
			}
		}
		return false
	}
	return true
}

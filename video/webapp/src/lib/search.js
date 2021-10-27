const TRANSLITERATIONS = {
	ä: 'ae',
	ö: 'oe',
	ü: 'ue',
	ß: 'ss'
}

export function phonyMatcher (searchTerm) {
	function normalize (value) {
		return value
			.replace(/[äöüß]/g, (char) => TRANSLITERATIONS[char])
			.replace(/[\s_\-,;.:/\\]+/g, ' ') // compact whitespace and separators
			.normalize('NFD').replace(/[^a-z0-9 ]/g, '') // scrape off diacritics
	}

	const needle = searchTerm.toLowerCase()
	const needleNorm = normalize(needle)

	return (term) => {
		const haystack = term.toLowerCase()
		if (haystack.includes(needle)) { // just lowercased match
			return true
		} else if (needleNorm) { // letter-based match
			return normalize(haystack).includes(needleNorm)
		}
	}
}

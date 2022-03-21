export function parseTraitGrants (grantsString) {
	return grantsString.split(',').map(
		(i) => i.trim().split('|').filter((j) => j.length > 0)
	).filter((i) => i.length > 0)
}

export function stringifyTraitGrants (grants) {
	return grants ? grants.map(i => (Array.isArray(i) ? i.join('|') : i)).join(', ') : ''
}

export function doesTraitsMatchGrants (traits, grants) {
	if (!grants || !traits || !Array.isArray(grants) || grants.length === 0) return false
	return grants.every(or => (Array.isArray(or) ? or.some(t => traits.includes(t)) : traits.includes(or)))
}

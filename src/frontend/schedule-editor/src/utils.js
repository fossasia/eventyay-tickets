// import i18n from 'i18n'

export function getLocalizedString (string) {
	if (typeof string === 'string') return string
	return Object.values(string)[0]
	// return string[i18n.locale] || string[i18n.fallbackLocale] || Object.values(string)[0]
}

const checkPropScrolling = (node, prop) => ['auto', 'scroll'].includes(getComputedStyle(node, null).getPropertyValue(prop))
const isScrolling = node => checkPropScrolling(node, 'overflow') || checkPropScrolling(node, 'overflow-x') || checkPropScrolling(node, 'overflow-y')
export function findScrollParent (node) {
	if (!node || node === document.body) return
	if (isScrolling(node)) return node
	return findScrollParent(node.parentNode)
}

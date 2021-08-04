import { createHash } from 'crypto'

const getHash = function (id) {
	const hash = createHash('md5')
	hash.update(id.toLowerCase().trim())
	return hash.digest('hex')
}

const getProfile = async function (hash) {
	return new Promise(function (resolve, reject) {
		const script = document.createElement('script')
		script.src = `https://gravatar.com/${hash}.json?callback=gravatarJSONP`
		const timeout = setTimeout(reject, 15000)
		window.gravatarJSONP = function (profile) {
			window.gravatarJSONP = undefined
			script.remove()
			clearTimeout(timeout)
			resolve(profile)
		}
		document.body.append(script)
	})
}

const getAvatarUrl = function (hash, size = 80) {
	return `https://gravatar.com/avatar/${hash}?s=${size}&d=404`
}

export { getHash, getProfile, getAvatarUrl }

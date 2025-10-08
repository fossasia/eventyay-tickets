// Avoid importing Node 'crypto' which Vite externalizes for the browser; use js-md5 instead
import md5 from 'js-md5'

const getHash = function(id) {
	// blueimp-md5 returns hex string
	return md5(id.toLowerCase().trim())
}

const getProfile = async function(hash) {
	return new Promise(function(resolve, reject) {
		const script = document.createElement('script')
		script.src = `https://gravatar.com/${hash}.json?callback=gravatarJSONP`
		const timeout = setTimeout(reject, 15000)
		window.gravatarJSONP = function(profile) {
			window.gravatarJSONP = undefined
			script.remove()
			clearTimeout(timeout)
			resolve(profile)
		}
		document.body.append(script)
	})
}

const getAvatarUrl = function(hash, size = 80) {
	return `https://gravatar.com/avatar/${hash}?s=${size}&d=404`
}

export { getHash, getProfile, getAvatarUrl }

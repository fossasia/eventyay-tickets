import md5hex from 'md5-hex'

const getHash = function (id) {
	return md5hex(id.toLowerCase().trim())
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

/* globals ENV_DEVELOPMENT */
import { helpers, required as _required, url as _url, integer as _integer } from '@vuelidate/validators'

const required = message => helpers.withMessage(message, _required)
const integer = message => helpers.withMessage(message, _integer)

const color = message => helpers.withMessage(message, helpers.regex('color', /^#([a-zA-Z0-9]{3}|[a-zA-Z0-9]{6})$/))

// The strictest regex for YouTube video IDs is probably [0-9A-Za-z_-]{10}[048AEIMQUYcgkosw]
// as per https://webapps.stackexchange.com/questions/54443/format-for-id-of-youtube-video
// but let's not count on YouTube not changing their format. Our main goal here is to prevent
// users from entering full URLs.
const youtubeid = message => helpers.withMessage(message, helpers.regex('youtubeid', /^[0-9A-Za-z_-]{5,}$/))

const relative = helpers.regex('relative', /^\/.*$/)
const devurl = helpers.regex('devurl', /^http:\/\/localhost.*$/) // vuelidate does not allow localhost
const url = message => helpers.withMessage(message, (value) => (!_required(value) || _url(value) || relative(value) || (ENV_DEVELOPMENT && devurl(value))))

const isJson = () => helpers.withMessage((ctx) => ctx?.$params?.message || 'Invalid JSON', (value) => {
	if (!value || value.length === 0) return true
	try {
		JSON.parse(value)
		return true
	} catch (exception) {
		// helpers.withMessage expects validator boolean; we can’t set dynamic message here easily,
		// so fall back to a generic message above.
		return false
	}
})

export {
	required,
	integer,
	color,
	url,
	youtubeid,
	isJson
}

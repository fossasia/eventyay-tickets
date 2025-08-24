/* globals ENV_DEVELOPMENT */
import {
	helpers,
	required as _required,
	maxLength as _maxLength,
	minLength as _minLength,
	email as _email,
	integer as _integer,
	maxValue as _maxValue,
	minValue as _minValue,
	url as _url
} from '@vuelidate/validators/dist/raw.mjs'

// Keep function names and export style as in main branch
export function required(message) {
	return helpers.withMessage(message, _required)
}
export function email(message) {
	return helpers.withMessage(message, _email)
}
export function maxLength(length, message) {
	return helpers.withMessage(message, _maxLength(length))
}
export function minLength(length, message) {
	return helpers.withMessage(message, _minLength(length))
}
export function integer(message) {
	return helpers.withMessage(message, _integer)
}
export function maxValue(maxVal, message) {
	return helpers.withMessage(message, _maxValue(maxVal))
}
export function minValue(minVal, message) {
	return helpers.withMessage(message, _minValue(minVal))
}
export function color(message) {
	return helpers.withMessage(message, helpers.regex(/^#([a-zA-Z0-9]{3}|[a-zA-Z0-9]{6})$/))
}
export function youtubeid(message) {
	return helpers.withMessage(message, helpers.regex(/^[0-9A-Za-z_-]{5,}$/))
}
const relative = helpers.regex(/^\/.*$/)
const devurl = helpers.regex(/^http:\/\/localhost.*$/) // vuelidate does not allow localhost
export function url(message) {
	return helpers.withMessage(message, (value) => (!helpers.req(value) || _url(value) || relative(value) || (ENV_DEVELOPMENT && devurl(value))))
}
export function isJson() {
	return helpers.withMessage(({ $response }) => $response?.message, value => {
		if (!value || value.length === 0) return { $valid: true }
		try {
			JSON.parse(value)
			return { $valid: true }
		} catch (exception) {
			return {
				$valid: false,
				message: exception.message
			}
		}
	})
}

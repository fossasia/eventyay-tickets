import { withParams, req } from 'vuelidate/lib/validators/common'
import { helpers, url as _url, integer as _integer } from 'vuelidate/lib/validators'

const required = message => withParams({message}, req)
const integer = message => withParams({message}, _integer)


const color = message => withParams({message}, helpers.regex('color', /^#([a-zA-Z0-9]{3}|[a-zA-Z0-9]{6})$/))

const relative = helpers.regex('relative', /^\/.*$/)
const devurl = helpers.regex('devurl', /^http:\/\/localhost.*$/) // vuelidate does not allow localhost
const url = message => withParams({message}, (value) => (!helpers.req(value) || _url(value) || relative(value) || (ENV_DEVELOPMENT && devurl(value))))

const isJson = () => withParams((addParams) => {
	return value => {
		if (!value || value.length === 0) return true
		try {
			JSON.parse(value)
			return true
		} catch (exception) {
			addParams({message: exception.message})
		}
		return false
	}
})

export {
	required,
	integer,
	color,
	url,
	isJson
}

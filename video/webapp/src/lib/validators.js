import { withParams, req } from 'vuelidate/lib/validators/common'
import { url as _url } from 'vuelidate/lib/validators'

const required = message => withParams({message}, req)

// TODO does not correctly detect localhost urls
const url = message => withParams({message}, _url)

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
	url,
	isJson
}

import { withParams, req } from 'vuelidate/lib/validators/common'
import { url as _url } from 'vuelidate/lib/validators'

const required = message => withParams({message}, req)

// TODO does not correctly detect localhost urls
const url = message => withParams({message}, _url)

export {
	required,
	url
}

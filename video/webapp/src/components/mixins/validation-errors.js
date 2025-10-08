export default {
	computed: {
		validationErrors() {
			return this.v$.$errors?.map(({ $message }) => $message) || []
		}
	}
}

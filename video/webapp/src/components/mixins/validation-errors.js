export default {
	computed: {
		validationErrors () {
			const errorMessages = []
			const extractErrors = ($v) => {
				const params = Object.values($v.$params)
				for (const param of params) {
					if (param?.message) errorMessages.push(param.message)
				}
			}
			const traverse = ($v) => {
				if (!$v.$error) return
				const values = Object.entries($v).filter(([key]) => !key.startsWith('$'))
				extractErrors($v)
				for (const [, value] of values) {
					if (typeof value === 'object') traverse(value)
				}
			}

			traverse(this.$v)
			return errorMessages
		}
	}
}

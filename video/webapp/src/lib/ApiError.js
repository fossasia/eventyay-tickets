class ApiError extends Error {
	constructor (apiError, ...params) {
		// Pass remaining arguments (including vendor specific ones) to parent constructor
		super(apiError.message || JSON.stringify(apiError.error), ...params)

		// Maintains proper stack trace for where our error was thrown (only available on V8)
		if (Error.captureStackTrace) {
			Error.captureStackTrace(this, ApiError)
		}

		this.name = 'APIError'
		// Custom debugging information
		this.apiError = apiError
	}
}

export default ApiError

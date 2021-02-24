export default {
	props: {
		config: {
			type: Object,
			required: true
		},
		modules: {
			type: Object,
			required: true
		}
	},
	methods: {
		addModule (type, config) {
			if (this.modules[type]) return
			this.config.module_config.push({
				type: type,
				config: config || {}
			})
		},
		removeModule (type) {
			const removeIndex = this.config.module_config.findIndex(m => m.type === type)
			if (removeIndex >= 0) {
				this.config.module_config.splice(removeIndex, 1)
			}
		}
	}
}

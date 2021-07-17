<script>
export default {
	props: {
		columnMinWidth: {
			type: Number,
			default: 360
		}
	},
	data () {
		return {
			contentRect: null
		}
	},
	async mounted () {
		await this.$nextTick()
		this.contentRect = this.$el.getBoundingClientRect()
		this.observer = new ResizeObserver(([{contentRect}]) => {
			this.contentRect = contentRect
		})
		this.observer.observe(this.$el)
	},
	beforeUnmount () {
		this.observer.disconnect()
	},
	methods: {},
	render (createElement) {
		const panels = this.$slots.default.slice()
		const panelCount = panels.length
		const columns = []
		if (this.contentRect) {
			const maxColumnCount = Math.floor(this.contentRect.width / this.columnMinWidth)
			const columnCount = Math.min(maxColumnCount, panelCount)
			for (let c = 0; c < columnCount; c++) {
				const columnItems = []
				const panelsToTake = Math.ceil(panels.length / (columnCount - c))
				for (let p = 0; p < panelsToTake; p++) {
					columnItems.push(panels.shift())
				}
				columns.push(createElement('div', {
					class: 'column'
				}, columnItems))
			}
		}
		return createElement('div', {
			class: 'c-dashboard-layout'
		}, columns)
	}
}
</script>
<style lang="stylus">
.c-dashboard-layout
	flex: auto
	display: flex
	min-height: 0
	min-width: 0
	> .column
		flex: 1 1 0px
		display: flex
		flex-direction: column
		min-height: 0
		min-width: 0
		&:not(:last-child)
			border-right: border-separator()
</style>

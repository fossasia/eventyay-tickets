<template lang="pug">
.c-scrollbars
	.scroll-content(ref="content", @scroll="onScroll")
		slot
	template(v-for="dim of Object.keys(dimensions)")
		div(:class="[`scrollbar-rail-${dim}`, {active: draggingDimension === dim}]", @pointerdown="onPointerdown(dim, $event)")
			.scrollbar-thumb(:ref="`thumb-${dim}`", :style="thumbStyles[dim]")
</template>
<script>
import ResizeObserver from 'resize-observer-polyfill'

export default {
	components: {},
	props: {
		y: Boolean,
		x: Boolean
	},
	data () {
		return {
			dimensions: null,
			draggingDimension: null,
			draggingOffset: null
		}
	},
	computed: {
		thumbStyles () {
			const thumbStyles = {}
			if (this.dimensions?.x) {
				thumbStyles.x = {
					width: this.dimensions.x.thumbLength + 'px',
					left: this.dimensions.x.thumbPosition + 'px'
				}
				if (this.dimensions.x.visibleRatio >= 1) {
					thumbStyles.x.display = 'none'
				}
			}
			if (this.dimensions?.y) {
				const direction = this.dimensions.y.direction === 'reverse' ? 'bottom' : 'top'
				thumbStyles.y = {
					height: this.dimensions.y.thumbLength + 'px',
					[direction]: this.dimensions.y.thumbPosition + 'px'
				}
				if (this.dimensions.y.visibleRatio >= 1) {
					thumbStyles.y.display = 'none'
				}
			}
			return thumbStyles
		}
	},
	created () {
		const dimensions = {}
		if (this.x) {
			dimensions.x = {
				visibleRatio: null,
				thumbLength: null,
				thumbPosition: null
			}
		}
		if (this.y) {
			dimensions.y = {
				visibleRatio: null,
				thumbLength: null,
				thumbPosition: null,
				direction: null
			}
		}
		this.dimensions = dimensions
	},
	async mounted () {
		await this.$nextTick()
		// setting direction once should be good enough
		if (this.dimensions.y) {
			const contentStyle = window.getComputedStyle(this.$refs.content)
			if (contentStyle.flexDirection.endsWith('reverse')) {
				this.dimensions.y.direction = 'reverse'
			}
		}
		this.computeDimensions()
		this.computeThumbPositions()
		this.resizeObserver = new ResizeObserver(this.onResize)
		this.resizeObserver.observe(this.$refs.content)
		for (const el of this.$refs.content.children) {
			this.resizeObserver.observe(el)
		}
		this.mutationObserver = new MutationObserver((records) => {
			for (const record of records) {
				for (const addedNode of record.addedNodes) {
					if (addedNode.nodeType !== Node.ELEMENT_NODE) continue
					this.resizeObserver.observe(addedNode)
				}
				for (const removedNode of record.removedNodes) {
					if (removedNode.nodeType !== Node.ELEMENT_NODE) continue
					this.resizeObserver.unobserve(removedNode)
				}
			}
			this.onResize()
		})
		this.mutationObserver.observe(this.$refs.content, {
			childList: true
		})
	},
	beforeDestroy () {
		this.resizeObserver.disconnect()
		this.mutationObserver.disconnect()
	},
	methods: {
		onScroll (event) {
			this.$emit('scroll', event)
			this.computeThumbPositions()
		},
		onResize () {
			this.computeDimensions()
			this.computeThumbPositions()
		},
		onPointerdown (dimension, $event) {
			const el = this.$refs[`thumb-${dimension}`][0]
			event.stopPropagation()
			el.setPointerCapture(event.pointerId)
			this.draggingDimension = dimension
			this.draggingOffset = event[`offset${dimension.toUpperCase()}`]
			// TODO cancel
			el.addEventListener('pointermove', this.onPointermove)
			el.addEventListener('pointerup', this.onPointerup)
		},
		onPointermove () {
			if (this.draggingDimension === 'x') {
				const maxX = this.$refs.content.clientWidth - this.dimensions.x.thumbLength
				const newPosition = event.clientX - this.$refs.content.getBoundingClientRect().left - this.draggingOffset
				this.dimensions.x.thumbPosition = Math.min(Math.max(0, newPosition), maxX)
				this.$refs.content.scrollLeft = this.dimensions.x.thumbPosition / maxX * (this.$refs.content.scrollWidth - this.$refs.content.clientWidth)
			}

			if (this.draggingDimension === 'y') {
				const maxY = this.$refs.content.clientHeight - this.dimensions.y.thumbLength
				if (this.dimensions.y.direction === 'reverse') {
					const newPosition = this.$refs.content.clientHeight - (event.clientY - this.$refs.content.getBoundingClientRect().top + (this.dimensions.y.thumbLength - this.draggingOffset))
					this.dimensions.y.thumbPosition = Math.min(Math.max(0, newPosition), maxY)
					this.$refs.content.scrollTop = -1 * this.dimensions.y.thumbPosition / maxY * (this.$refs.content.scrollHeight - this.$refs.content.clientHeight)
				} else {
					const newPosition = event.clientY - this.$refs.content.getBoundingClientRect().top - this.draggingOffset
					this.dimensions.y.thumbPosition = Math.min(Math.max(0, newPosition), maxY)
					this.$refs.content.scrollTop = this.dimensions.y.thumbPosition / maxY * (this.$refs.content.scrollHeight - this.$refs.content.clientHeight)
				}
			}
		},
		onPointerup (event) {
			const dimension = this.draggingDimension
			const el = this.$refs[`thumb-${dimension}`][0]
			this.draggingDimension = null
			el.releasePointerCapture(event.pointerId)
			el.removeEventListener('pointermove', this.onPointermove)
			el.removeEventListener('pointerup', this.onPointerup)
		},
		computeDimensions () {
			if (this.dimensions.x) {
				this.dimensions.x.visibleRatio = this.$refs.content.clientWidth / this.$refs.content.scrollWidth
				this.dimensions.x.thumbLength = this.$refs.content.clientWidth * this.dimensions.x.visibleRatio
			}
			if (this.dimensions.y) {
				this.dimensions.y.visibleRatio = this.$refs.content.clientHeight / this.$refs.content.scrollHeight
				this.dimensions.y.thumbLength = this.$refs.content.clientHeight * this.dimensions.y.visibleRatio
			}
		},
		computeThumbPositions () {
			if (this.dimensions.x) {
				this.dimensions.x.thumbPosition = this.$refs.content.scrollLeft / (this.$refs.content.scrollWidth - this.$refs.content.clientWidth) * (this.$refs.content.clientWidth - this.dimensions.x.thumbLength)
			}
			if (this.dimensions.y) {
				if (this.dimensions.y.direction === 'reverse') {
					this.dimensions.y.thumbPosition = -1 * this.$refs.content.scrollTop / (this.$refs.content.scrollHeight - this.$refs.content.clientHeight) * (this.$refs.content.clientHeight - this.dimensions.y.thumbLength)
				} else {
					this.dimensions.y.thumbPosition = this.$refs.content.scrollTop / (this.$refs.content.scrollHeight - this.$refs.content.clientHeight) * (this.$refs.content.clientHeight - this.dimensions.y.thumbLength)
				}
			}
		},
		updateThumb (dimension) {
			const state = this[dimension]
			if (!state) return
			if (state.visibleRatio >= 1) {
				state.thumbEl.style.display = 'none'
			} else {
				state.thumbEl.style.display = null
				if (dimension === 'x') {
					state.railEl.style.width = state.railLength + 'px'
					state.thumbEl.style.width = state.thumbLength + 'px'
					state.thumbEl.style.left = state.thumbPosition + 'px'
				} else if (dimension === 'y') {
					state.railEl.style.height = state.railLength + 'px'
					state.thumbEl.style.height = state.thumbLength + 'px'
					state.thumbEl.style.top = state.thumbPosition + 'px'
				}
			}
		}
	}
}
</script>
<style lang="stylus">
$rail-width = 15px
$thumb-width = 6px
$thumb-width-hovered = 12px

.c-scrollbars
	display: flex;
	flex-direction: column
	position: relative
	box-sizing: border-box
	min-height: 0
	.scroll-content
		display: flex
		flex-direction: column
		overflow: scroll
		min-height: 0
		&::-webkit-scrollbar
			display: none
		scrollbar-width: none

	&:hover
		.scrollbar-thumb
			opacity: .4

	.scrollbar-rail-x,
	.scrollbar-rail-y
		position: absolute
		user-select: none
		overflow: hidden

	.scrollbar-thumb
		position: absolute
		background-color: $clr-blue-grey-600
		opacity: .2
		border-radius: $thumb-width
		transition: height .3s $material-easing, width .3s $material-easing, opacity .3s $material-easing

	.scrollbar-rail-x
		height: $rail-width
		width: 100%
		bottom: 0
		.scrollbar-thumb
			bottom: 2px
			height: $thumb-width

		&:hover, &.active
			.scrollbar-thumb
				height: $thumb-width-hovered
				opacity: .8
	.scrollbar-rail-y
		width: $rail-width
		height: 100%
		right: 0
		top: 0

		.scrollbar-thumb
			right: 2px
			width: $thumb-width
		&:hover, &.active
			.scrollbar-thumb
				width: $thumb-width-hovered
				opacity: .8
</style>

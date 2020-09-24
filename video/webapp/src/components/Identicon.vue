<template lang="pug">
.c-identicon
	svg(:viewBox="`0 0 ${2*Math.sqrt(2)} ${2*Math.sqrt(2)}`")
		g(:transform="`translate(0.125 ${Math.sqrt(2)}) scale(.9 .9) rotate(-45 0 0)`")
			g.shape(transform="translate(1 0)", :class="shape.class")
				circle(v-if="shape.class === 'circle'", cx=".65", cy=".35", r=".325", :style="shape.style")
				path(v-else, :d="shape.path", :style="shape.style", :transform="shape.transform")
			g.block(v-for="block of blocks", :transform="`translate(${block.pos.x} ${block.pos.y})`")
				path(v-for="path of block.paths", :d="path.d", :style="{fill: path.color, 'mix-blend-mode': 'multiply'}")
				path.stroke(d="M 0 0 L 0 1 L 1 1 L 1 0z", style="fill: none; stroke: black; stroke-width: 0.125; stroke-lineend: round; stroke-linejoin: round; mix-blend-mode: multiply;")
</template>
<script>
// ported from https://github.com/Schlipak/IdentiHeart
const PALETTE = [
	'#F44336', '#E91E63', '#9C27B0', '#673AB7', '#3F51B5', '#2196F3',
	'#03A9F4', '#00BCD4', '#009688', '#4CAF50', '#8BC34A', '#CDDC39',
	'#FFEB3B', '#FFC107', '#FF9800', '#FF5722', '#795548', '#607D8B'
]

const hashFunc = function (source) {
	return String(source).split('').reduce(function (a, b) {
		a = ((a << 5) - a) + b.charCodeAt(0)
		return a & a
	}, 0)
}

export default {
	props: {
		id: String
	},
	computed: {
		hash () {
			return hashFunc(this.id)
		},
		primaryColor () {
			return PALETTE[Math.abs(this.hash % PALETTE.length)]
		},
		accentColor () {
			return PALETTE[Math.abs(hashFunc(this.hash) % PALETTE.length)]
		},
		shape () {
			const createPath = (offset) => {
				const mod = Math.abs(this.hash + 1) % 4
				const color = [this.primaryColor, this.accentColor][Math.abs(this.hash % 2)]
				const commonStyle = {fill: color, stroke: 'black', 'stroke-width': 0.125, 'stroke-lineend': 'round', 'stroke-linejoin': 'round', 'mix-blend-mode': 'multiply'}
				switch (mod) {
					case 1:
						return {class: 'circle', style: {'stroke-width': 0.11, ...commonStyle}}
					case 2:
						return {class: 'triangle', path: 'M 0 0 L 0 1 L 1 1z', transform: 'scale(0.7, 0.7) translate(0.6, -0.15)', style: {'stroke-width': 0.15, ...commonStyle}}
					case 3:
						return {class: 'oval', path: 'M 0 1 Q .2 .2 1 0 Q .8 .8 0 1z', transform: 'scale(0.7, 0.7) translate(0.3, 0.1)', style: {...commonStyle}}
					default:
						return {class: 'square', path: 'M 0 0 L 0 1 L 1 1 L 1 0z', transform: 'scale(0.5, 0.5) translate(0.75, 0.2)', style: {'stroke-width': 0.2, ...commonStyle}}
				}
			}
			return {
				...createPath()
			}
		},
		blocks () {
			const createPath = (offset) => {
				const mod = Math.abs(this.hash + offset) % 4
				switch (mod) {
					case 0: // top
						return 'M 0 0 L 1 0 L 1 1'
					case 1: // right
						return 'M 1 0 L 1 1 L 0 1'
					case 2: // bottom
						return 'M 0 0 L 0 1 L 1 1'
					case 3: // left
						return 'M 0 0 L 1 0 L 0 1'
					default: // top
						return 'M 0 0 L 1 0 L 0 1'
				}
			}
			return [{
				pos: {x: 0, y: 0},
				paths: [
					{d: createPath(this.hash % 3), color: this.primaryColor},
					{d: createPath(this.hash % 5), color: this.accentColor}
				]
			}, {
				pos: {x: 0, y: 1},
				paths: [
					{d: createPath(this.hash % 4), color: this.accentColor},
					{d: createPath(this.hash % 3), color: this.primaryColor}
				]
			}, {
				pos: {x: 1, y: 1},
				paths: [
					{d: createPath(this.hash % 7), color: this.accentColor},
					{d: createPath(this.hash % 8), color: this.primaryColor}
				]
			}]
		}
	}
}
</script>
<style lang="stylus">
.c-identicon
	user-select: none
</style>

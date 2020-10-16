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

export function getIdenticonSVG (id) {
	const hash = hashFunc(id)
	const primaryColor = PALETTE[Math.abs(hash % PALETTE.length)]
	const accentColor = PALETTE[Math.abs(hashFunc(hash) % PALETTE.length)]

	const createShape = () => {
		const mod = Math.abs(hash + 1) % 4
		switch (mod) {
			case 1:
				return {class: 'circle'}
			case 2:
				return {class: 'triangle', path: 'M 0 0 L 0 1 L 1 1z', transform: 'scale(0.7 0.7) translate(0.6 -0.15)'}
			case 3:
				return {class: 'oval', path: 'M 0 1 Q .2 .2 1 0 Q .8 .8 0 1z', transform: 'scale(0.7 0.7) translate(0.3 0.1)'}
			default:
				return {class: 'square', path: 'M 0 0 L 0 1 L 1 1 L 1 0z', transform: 'scale(0.5 0.5) translate(0.75 0.2)'}
		}
	}
	const shape = {
		color: [primaryColor, accentColor][Math.abs(hash % 2)],
		...createShape()
	}

	const createBlock = (offset) => {
		const mod = Math.abs(hash + offset) % 4
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

	const blocks = [{
		pos: {x: 0, y: 0},
		paths: [
			{d: createBlock(hash % 3), color: primaryColor},
			{d: createBlock(hash % 5), color: accentColor}
		]
	}, {
		pos: {x: 0, y: 1},
		paths: [
			{d: createBlock(hash % 4), color: accentColor},
			{d: createBlock(hash % 3), color: primaryColor}
		]
	}, {
		pos: {x: 1, y: 1},
		paths: [
			{d: createBlock(hash % 7), color: accentColor},
			{d: createBlock(hash % 8), color: primaryColor}
		]
	}]

	const renderShape = () => {
		if (shape.class === 'circle') {
			return `<circle cx="0.65" cy="0.35" r="0.325" style="fill: ${shape.color}"/>`
		} else {
			return `<path d="${shape.path}" style="fill: ${shape.color}" transform="${shape.transform}"/>`
		}
	}

	const renderPath = path => `<path d="${path.d}" style="fill: ${path.color}"/>`

	const renderBlock = block => {
		return `<g class="block" transform="translate(${block.pos.x} ${block.pos.y})">${block.paths.map(renderPath).join('')}<path class="stroke" d="M 0 0 L 0 1 L 1 1 L 1 0z"/></g>`
	}

	return `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${2 * Math.sqrt(2)} ${2 * Math.sqrt(2)}">
	<style>
		path {
			mix-blend-mode: multiply;
		}
		.stroke {
			fill: none;
			stroke: black;
			stroke-width: 0.125;
			stroke-lineend: round;
			stroke-linejoin: round;
		}
		.shape circle, .shape path {
			stroke: black;
			stroke-width: 0.125;
			stroke-lineend: round;
			stroke-linejoin: round;
		}
		.shape circle {
			stroke-width: 0.11;
		}
		.shape.square path {
			stroke-width: 0.2;
		}
		.shape.triangle path {
			stroke-width: 0.15;
		}
	</style>
	<g transform="translate(0.125 ${Math.sqrt(2)}) scale(.9 .9) rotate(-45 0 0)">
		<g class="shape ${shape.class}" transform="translate(1 0)">
			${renderShape()}
		</g>
		${blocks.map(renderBlock).join('')}
	</g>
</svg>
`
}

export function getIdenticonSvgUrl (id) {
	return `data:image/svg+xml;base64,${btoa(getIdenticonSVG(id).replace(/[\t\n]/g, ''))}`
}

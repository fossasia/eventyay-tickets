export const definition = {
	label: 'Initials',
	colorPalette: {
		size: 14,
		defaults: [
			'#ffcdd2',
			'#f8bbd0',
			'#e1bee7',
			'#d1c4e9',
			'#c5cae9',
			'#b2dfdb',
			'#A0F2B7',
			'#f0f4c3',
			'#fff9c4',
			'#ffecb3',
			'#ffe0b2',
			'#ffccbc',
			'#d7ccc8',
			'#cfd8dc',
		],
	},
}

export function renderSvg (random, userProfile, config) {
	const calculateHSLColor = (hex, addH, addS, addL, setL) => {
		// Convert hex to RGB first
		let r = 0
		let g = 0
		let b = 0
		if (hex.length === 4) {
			r = '0x' + hex[1] + hex[1]
			g = '0x' + hex[2] + hex[2]
			b = '0x' + hex[3] + hex[3]
		} else if (hex.length === 7) {
			r = '0x' + hex[1] + hex[2]
			g = '0x' + hex[3] + hex[4]
			b = '0x' + hex[5] + hex[6]
		}
		// Then to HSL
		r /= 255
		g /= 255
		b /= 255
		const cmin = Math.min(r, g, b)
		const cmax = Math.max(r, g, b)
		const delta = cmax - cmin
		let h = 0
		let s = 0
		let l = 0

		if (delta === 0) h = 0
		else if (cmax === r) h = ((g - b) / delta) % 6
		else if (cmax === g) h = (b - r) / delta + 2
		else h = (r - g) / delta + 4

		h = Math.round(h * 60)

		if (h < 0) h += 360

		l = (cmax + cmin) / 2
		s = delta === 0 ? 0 : delta / (1 - Math.abs(2 * l - 1))
		s = +(s * 100).toFixed(1) - 10
		l = +(l * 100).toFixed(1) - 10

		if (addH && addS && addL && !setL) {
			// calculateNewColor
			h = (h + addH) % 360
			s = (s + addS) % 100
			l = (l + addL) % 100
		}

		if (setL) {
			l = setL
		}

		return 'hsl(' + h + ',' + s + '%,' + l + '%)'
	}

	const sliceNameToInitials = (name) => {
		return name
			.split(' ')
			.map((n) => n[0])
			.join('')
			.slice(0, 2)
	}

	var initials = sliceNameToInitials(userProfile.display_name)
	var bgColor =
		config.colorPalette[
			random.integer(0, config.colorPalette.length - 1)
		]
	var secondColor = calculateHSLColor(bgColor, -28, -5, -22)
	var textColor = calculateHSLColor(bgColor, 0, 0, 0, 95)
	var size = 48
	var fontFamily =
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif"
	var fontSize = 0.5
	var fontWeight = 500

	return `
	<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}">
		<defs>
			<radialGradient id="gradient" cx="0" cy="0" r="1" gradientTransform="scale(1.5)">
				<stop stop-color="${bgColor}" />
				<stop offset="1" stop-color="${secondColor}" />
			</radialGradient>
		</defs>	
		<circle fill="url(#gradient)" cx="${size / 2}" cy="${size / 2}" r="${
	size / 2
}"/>
		<text x="50%" y="50%" style="color: ${textColor};line-height: 1;font-family: ${fontFamily};" alignment-baseline="middle" text-anchor="middle" font-size="${Math.round(
	size * fontSize
)}" font-weight="${fontWeight}" dy=".1em" dominant-baseline="middle" fill="${textColor}">${initials}</text>
	</svg>
	`
}
